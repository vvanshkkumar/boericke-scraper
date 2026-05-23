import argparse
import html as html_lib
import json
import logging
import os
import random
import re
import time
from collections import Counter
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup, NavigableString

BASE_URL = "http://homeoint.org/books/boericmm/"
LETTERS = list("abcdefghijklmnopqrstuvwxyz")
DEFAULT_OUTPUT = "boericke_remedies.json"
FAILED_URLS_FILE = "failed_urls.txt"
LOG_FILE = "scraper.log"
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ── Logging ──────────────────────────────────────────────────────────────────

def _setup_logging() -> logging.Logger:
    logger = logging.getLogger("boericke")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)-7s] %(message)s", datefmt="%H:%M:%S")
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(console)
    logger.addHandler(fh)
    return logger

log = _setup_logging()

# ── Text helpers ────────────────────────

def clean_text(text: str) -> str:
    """Unescape HTML entities, collapse whitespace."""
    if not text:
        return ""
    text = html_lib.unescape(text)
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\xa0", " ", text)         
    text = re.sub(r" {2,}", " ", text)
    return text.strip()

# ── Bonus: potency extraction ──────────────────────────────────────

ORDINAL_TO_NUM = {
    "first": "1", "second": "2", "third": "3", "fourth": "4", 
    "fifth": "5", "sixth": "6", "seventh": "7", "eighth": "8",
    "ninth": "9", "tenth": "10", "twelfth": "12", 
    "thirtieth": "30", "two-hundredth": "200", "two hundredth": "200"
}

def extract_potencies(dose_text: str) -> list[str]:
    """Extract potency strings (e.g. '30c', '6x') from the Dose section."""
    potencies = []
    
    # Catch numeric formats like 3x, 30c, 200c
    numeric = re.findall(r"\b(\d+\s*[xXcCmM])\b", dose_text)
    potencies.extend(p.replace(" ", "").lower() for p in numeric)
    
    lower = dose_text.lower()
    
    # Catch ordinal words
    for word, num in ORDINAL_TO_NUM.items():
        if re.search(r"\b" + re.escape(word) + r"\b", lower):
            potencies.append(num)
            
    # Catch tinctures
    if re.search(r"\b(tincture|mother tincture|m\.t\.)\b", lower):
        potencies.append("Tincture")
        
    # Deduplicate while preserving order
    seen = set()
    return [p for p in potencies if not (p in seen or seen.add(p))]

# ── Bonus: keyword extraction ────────────────────────────────

STOPWORDS = {
    "the", "and", "with", "from", "that", "this", "are", "for",
    "not", "have", "has", "been", "more", "also", "when", "after",
    "dose", "potency", "remedy", "compare", "first", "third",
}

def extract_keywords(text: str, top_n: int = 10) -> list[str]:
    """Return the top_n most frequent meaningful words from combined text."""
    tokens = re.findall(r"\b[a-z]{4,}\b", text.lower())
    meaningful = [t for t in tokens if t not in STOPWORDS]
    return [w for w, _ in Counter(meaningful).most_common(top_n)]

# ── HTTP helpers ────────────────────────────────

def fetch_with_retry(url: str, max_retries: int = MAX_RETRIES) -> Optional[str]:
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
            resp.encoding = "latin-1"
            if resp.status_code == 200:
                return resp.text
            log.debug(f"Attempt {attempt}: HTTP {resp.status_code} for {url}")
        except requests.RequestException as exc:
            log.debug(f"Attempt {attempt}/{max_retries}: {exc}")
        if attempt < max_retries:
            time.sleep(RETRY_BACKOFF_BASE ** attempt)
    return None

def log_failed_url(url: str, reason: str = "") -> None:
    with open(FAILED_URLS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{url} | {reason}\n")

# ── Letter index ──────────────────────────────────────────────────────────────

def fetch_letter_index(letter: str) -> Optional[str]:
    url = f"{BASE_URL}{letter}.htm"
    html = fetch_with_retry(url)
    if html is None:
        log_failed_url(url, reason="Letter index unreachable")
    return html

def parse_remedy_links(html: str, letter: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    blockquote = soup.find("blockquote")
    if not blockquote:
        return results

    letter_prefix = f"{letter}/"
    for a_tag in blockquote.find_all("a", href=True):
        href = a_tag["href"].strip()
        abbrev = a_tag.get_text(strip=True)
        if not href.lower().startswith(letter_prefix.lower()):
            continue
        if not abbrev or len(abbrev) < 2:
            continue
        results.append({
            "abbreviation": abbrev.upper(),
            "url": BASE_URL + href,
        })
    return results

# ── Remedy page parsing ───────────────────────────────────────────────────────

def _extract_names(soup: BeautifulSoup) -> tuple[str, Optional[str]]:
    """Extract the full Latin name and optional common name cleanly."""
    full_name = ""
    common_name = None

    # 1. Extract Full Name cleanly from <title>
    title_tag = soup.find("title")
    if title_tag:
        title_text = clean_text(title_tag.get_text())
        parts = re.split(r"\s+-\s+", title_text)
        # Filter out Boericke's boilerplate strings
        name_parts = [p.strip() for p in parts if not any(x in p.upper() for x in ["HOMEOPATHIC", "HOMOEOPATHIC", "BOERICKE", "MATERIA"])]
        full_name = "-".join(name_parts).strip()

    # 2. Extract Common Name surgically from the <b> tag
    for b in soup.find_all("b"):
        font = b.find("font")
        
        if font and (font.get("size") == "5" or font.get("color") == "#800000"):
           
            for child in b.children:
                if isinstance(child, NavigableString):
                    text = clean_text(str(child))
                    # Common names have lowercase letters 
                    if text and len(text) > 2 and re.search(r'[a-z]', text):
                        common_name = text
                        break
        if common_name:
            break

    return full_name, common_name

def _extract_general_and_sections(
    soup: BeautifulSoup,
    full_name: str,
    common_name: Optional[str],
) -> tuple[str, dict[str, str]]:
    """Use strict text-block line analysis to prevent website noise leakage."""
    content_tag = soup.body or soup
    
    for unwanted in content_tag.find_all(["script", "style", "a"]):
        unwanted.decompose()

    
    raw_text = content_tag.get_text(separator="\n")
    lines = [clean_text(line) for line in raw_text.split('\n')]
    
    valid_lines = []
    
   
    boilerplate_exact = ["home", "main"]
    boilerplate_partial = [
        "materia medica", "william boericke", "presented by", "médi-t", 
        "copyright", "preface to the", "remedies and their", 
        "repertory", "search: key =", "remerciements", "photographie"
    ]
    
    
    full_name_clean = re.sub(r'[^a-zA-Z]', '', full_name).lower() if full_name else "xyz"
    
    # Filter the document line-by-line
    for line in lines:
        if not line: continue
        line_lower = line.lower()
        
       
        if line_lower in boilerplate_exact:
            continue
            
       
        if any(b in line_lower for b in boilerplate_partial) and len(line) < 100:
            continue
            
       
        if re.match(r'^([A-Z\*\s]+)$', line):
            continue
            
       
        line_clean = re.sub(r'[^a-zA-Z]', '', line).lower()
        if line_clean == full_name_clean:
            continue
            
       
        if common_name and line.strip().lower() == common_name.strip().lower():
            continue
            
        valid_lines.append(line)

    text_body = "\n".join(valid_lines)
    
    # Split the document by Section Headers (e.g., "\nHead.--" or "\nStomach.--")
    section_pattern = re.compile(r'\n([A-Z][a-zA-Z\s/\-]{1,30})\.--')
    parts = section_pattern.split(text_body)
    
    
    general = parts[0].replace("\n", " ").strip()
    
    sections = {}
    for i in range(1, len(parts), 2):
        key = parts[i].strip()
      
        val = parts[i+1].replace("\n", " ").strip()
        
       
        val = re.sub(r'\s*Copyright\s*©.*$', '', val, flags=re.IGNORECASE).strip()
        val = re.sub(r'\s*Home$', '', val, flags=re.IGNORECASE).strip()
        
        if key and val:
            sections[key] = val

    return general, sections

def _extract_relationships(sections: dict[str, str]) -> Optional[str]:
    """Pop and return the Relationships section, if present."""
    for key in list(sections.keys()):
        if key.lower().startswith("relationship"):
            val = sections.pop(key)
            return val if val else None
    return None

# ── Main scrape function ──────────────────────────────────────────────────────

def scrape_remedy_page(
    url: str,
    abbreviation: str,
    letter: str,
) -> Optional[dict]:
    html = fetch_with_retry(url)
    if html is None:
        log_failed_url(url, "Page fetch failed")
        return None

    soup = BeautifulSoup(html, "html.parser")

    full_name, common_name = _extract_names(soup)
    general, sections = _extract_general_and_sections(soup, full_name, common_name)
    relationships = _extract_relationships(sections)
    potencies = extract_potencies(sections.get("Dose", ""))
    
    combined = " ".join([general] + list(sections.values()))
    keywords = extract_keywords(combined)

    return {
        "abbreviation": abbreviation,
        "full_name": full_name,
        "common_name": common_name,
        "source_url": url,
        "letter": letter.upper(),
        "general": general,
        "sections": sections,
        "relationships": relationships,
        "potencies": potencies,
        "keywords": keywords,
    }

# ── I/O helpers and CLI ────────────────────────────────────────────────────────

def save_output(remedies: list[dict], filepath: str) -> None:
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(remedies, fh, ensure_ascii=False, indent=2)

def load_existing_output(filepath: str) -> list[dict]:
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, IOError) as exc:
        log.warning(f"Could not load existing output ({exc}). Starting fresh.")
        return []

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape Boericke's Homoeopathic Materia Medica into JSON."
    )
    parser.add_argument("--letter", type=str, default=None,
                        help="Scrape only this letter (e.g. --letter a)")
    parser.add_argument("--delay", type=float, default=None,
                        help="Fixed delay between requests (default: 0.5–1.0 s random)")
    parser.add_argument("--output", type=str, default=DEFAULT_OUTPUT)
    parser.add_argument("--upload", action="store_true",
                        help="Upload results to MongoDB after scraping")
    parser.add_argument("--mongo-uri", type=str, default="mongodb://localhost:27017/")
    args = parser.parse_args()

    letters_to_scrape = [args.letter.lower()] if args.letter else LETTERS

    all_remedies: list[dict] = load_existing_output(args.output)
    scraped_urls: set[str] = {r["source_url"] for r in all_remedies}
    start_time = datetime.now()

    for letter in letters_to_scrape:
        log.info(f"{'─' * 20} Letter {letter.upper()} {'─' * 20}")

        index_html = fetch_letter_index(letter)
        if index_html is None:
            log.error(f"Skipping letter '{letter.upper()}': index page failed.")
            continue

        remedy_links = parse_remedy_links(index_html, letter)
        if not remedy_links:
            log.warning(f"No remedy links found for letter '{letter.upper()}'.")
            continue

        total = len(remedy_links)
        count = 0

        for remedy in remedy_links:
            url = remedy["url"]
            abbrev = remedy["abbreviation"]

            if url in scraped_urls:
                count += 1
                continue

            data = scrape_remedy_page(url, abbrev, letter)

            if data:
                all_remedies.append(data)
                scraped_urls.add(url)
                count += 1
                display_name = data.get("full_name") or abbrev
                print(f"[{letter.upper()}] Scraped {count}/{total} - {display_name}")
            else:
                log.error(f"Failed to scrape: {url}")

            pause = args.delay if args.delay is not None else random.uniform(0.5, 1.0)
            time.sleep(pause)

        save_output(all_remedies, args.output)
        log.info(f"Letter {letter.upper()} done. {count}/{total} remedies saved.")

    save_output(all_remedies, args.output)

    elapsed = datetime.now() - start_time
    mins, secs = divmod(int(elapsed.total_seconds()), 60)

    print("\n" + "━" * 50)
    print("  Scrape Complete")
    print(f"  Total remedies scraped   : {len(all_remedies)}")
    print(f"  With common name         : {sum(1 for r in all_remedies if r.get('common_name'))}")
    print(f"  With relationships       : {sum(1 for r in all_remedies if r.get('relationships'))}")
    print(f"  Time taken               : {mins}m {secs}s")
    print(f"  Output saved to          : {args.output}")
    print("━" * 50 + "\n")

    if args.upload:
        _upload_to_mongo(all_remedies, args.mongo_uri)

def _upload_to_mongo(remedies: list[dict], uri: str) -> None:
    try:
        from pymongo import MongoClient
        client = MongoClient(uri)
        col = client["jarvis"]["remedies"]
        col.delete_many({})
        col.insert_many(remedies)
        print(f"Uploaded {len(remedies)} remedies to MongoDB.")
    except Exception as exc:
        log.error(f"MongoDB upload failed: {exc}")
   


if __name__ == "__main__":
    main()