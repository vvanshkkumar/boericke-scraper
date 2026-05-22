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
RETRY_BACKOFF_BASE = 2 # wait : 2s, 4s, 8s
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
SITE_HEADER_SIGNALS = ("MATERIA MEDICA", "BOERICKE", "Presented by", "di-T")

# Splits HTML on section headers like <b>Mind.--</b>
SECTION_SPLIT_RE = re.compile(
r"<b[^>]*>([A-Z][A-Za-z\s/\-]+?)\.--\s*</b>",
re.IGNORECASE,
)

# ----- # logging fucntion

def _setup_logging() -> logging.Logger:
    logger = logging.getLogger("boericke")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(message)s",
        datefmt="%H:%M:%S"
    )

    # Console: INFO and above
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)

    # File: DEBUG and above
    file_handler = logging.FileHandler(
        LOG_FILE,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)

    logger.addHandler(console)
    logger.addHandler(file_handler)

    return logger


log = _setup_logging()


# -------- # Text cleaning functions


def clean_text(text: str) -> str:
    if not text:
        return ""

    # Convert like (&amp; -> &, &#233; -> é)
    text = html_lib.unescape(text)

   
    text = re.sub(r"[\r\n\t]+", " ", text)

    
    text = re.sub(r" {2,}", " ", text)

    return text.strip()


def strip_html_tags(fragment: str) -> str:
    """
    <b>word</b><i>word2</i>
    becomes:
    word word2

    """


    cleaned = re.sub(r"<[^>]+>", " ", fragment)

    
    return clean_text(cleaned)


# ------ # Potency Extraction

ORDINAL_TO_NUM = {
    "first": "1",
    "third": "3",
    "sixth": "6",
    "thirtieth": "30",
    "two-hundredth": "200",
}


def extract_potencies(dose_text: str) -> list[str]:
    potencies = []

    # Numeric potencies: "30c", "6x", "200c", "1m"
    numeric = re.findall(
        r"\b(\d+\s*[xXcCmM])\b",
        dose_text
    )

    # Clean results:
    # "30 c" -> "30c"
    # "6X" -> "6x"
    potencies.extend(
        p.replace(" ", "").lower()
        for p in numeric
    )

   
    # "third" -> "3"
    # "thirtieth" -> "30"
    lower_text = dose_text.lower()

    for word, number in ORDINAL_TO_NUM.items():
        if re.search(
            r"\b" + re.escape(word) + r"\b",
            lower_text
        ):
            potencies.append(number)

    
    seen = set()
    unique = []

    for p in potencies:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    return unique

# ----- # Symptomn Extraction

from collections import Counter


STOPWORDS = {
    "the", "a", "an", "and", "or",
    "with", "from", "dose",
    "potency", "remedy", "compare"
}


def extract_keywords(
    text: str,
    top_n: int = 10
) -> list[str]:


    tokens = re.findall(
        r"\b[a-z]{4,}\b",
        text.lower()
    )

    
    meaningful = [
        t for t in tokens
        if t not in STOPWORDS
    ]

    
    counter = Counter(meaningful)


    return [
        word
        for word, _ in counter.most_common(top_n)
    ]

# ---- # fetch with retry such as 2s 4s 8s wait

def fetch_with_retry(
    url: str,
    max_retries: int = 3
) -> Optional[str]:

    for attempt in range(1, max_retries + 1):

        try:
            response = requests.get(
                url,
                headers=REQUEST_HEADERS,
                timeout=15
            )

          
            response.encoding = "latin-1"

           
            if response.status_code == 200:
                return response.text

        except requests.RequestException as exc:
            log.debug(
                f"Attempt {attempt}/{max_retries}: {exc}"
            )

     
        if attempt < max_retries:
            wait = (
                RETRY_BACKOFF_BASE ** attempt
            )  # 2, 4, 8 sec

            time.sleep(wait)

   
    return None

# ----- # fetching letter page


def log_failed_url(
    url: str,
    reason: str = ""
) -> None:
    """
    Save failed URLs so they can
    be retried later.
    """

    with open(
        FAILED_URLS_FILE,
        "a",
        encoding="utf-8"
    ) as f:

        f.write(
            f"{url} | {reason}\n"
        )

def fetch_letter_index(
    letter: str
) -> Optional[str]:
    """
    Example:
    letter="a"
    fetches:
    http://homeoint.org/books/boericmm/a.htm
    """

    url = f"{BASE_URL}{letter}.htm"

    html = fetch_with_retry(url)

    if html is None:
        log_failed_url(
            url,
            reason="Letter index unreachable"
        )

    return html

# ---- # 

def parse_remedy_links(
    html: str,
    letter: str
) -> list[dict]:

    soup = BeautifulSoup(
        html,
        "lxml"
    )

    results = []

    blockquote = soup.find(
        "blockquote"
    )

    if not blockquote:
        return results

   
    letter_prefix = f"{letter}/"

    for a_tag in blockquote.find_all(
        "a",
        href=True
    ):

        href = (
            a_tag["href"]
            .strip()
        )

        abbrev = a_tag.get_text(
            strip=True
        )

       
        if not href.lower().startswith(
            letter_prefix.lower()
        ):
            continue

    
        if (
            not abbrev
            or len(abbrev) < 2
        ):
            continue

        results.append({
            "abbreviation":
            abbrev.upper(),

            "url":
            BASE_URL + href
        })

    return results

# ---- # Extract all details (core function)

def scrape_remedy_page(
    url: str,
    abbreviation: str,
    letter: str
) -> Optional[dict]:

    
    html = fetch_with_retry(url)

    if html is None:
        log_failed_url(
            url,
            "Page fetch failed"
        )
        return None

    soup = BeautifulSoup(
        html,
        "lxml"
    )

    
    full_name, common_name = (
        _extract_names(soup)
    )


    general, sections = (
        _extract_general_and_sections(
            soup,
            full_name,
            common_name
        )
    )

   
    relationships = (
        _extract_relationships(
            sections
        )
    )

    
    potencies = extract_potencies(
        sections.get("Dose", "")
    )

    combined = " ".join(
        [general]
        + list(sections.values())
    )

    keywords = extract_keywords(
        combined
    )

    return {
        "abbreviation":
        abbreviation,

        "full_name":
        full_name,

        "common_name":
        common_name,

        "source_url":
        url,

        "letter":
        letter.upper(),

        "general":
        general,

        "sections":
        sections,

        "relationships":
        relationships,

        "potencies":
        potencies,

        "keywords":
        keywords,
    }

def clean_section_name(raw: str) -> str:
    name = raw.strip()
    name = re.sub(r"\.?-+$", "", name)
    name = re.sub(r"\.$", "", name)
    return name.strip()


def _extract_names(soup: BeautifulSoup) -> tuple[str, Optional[str]]:
    blockquote = soup.find("blockquote") or soup

    for b_tag in blockquote.find_all("b"):
        raw = b_tag.get_text(separator="\n")

        # Skip the site header bold tag
        if any(sig.lower() in raw.lower() for sig in SITE_HEADER_SIGNALS):
            continue

        # Stop at section headers
        stripped = raw.strip()
        if re.match(r"^[A-Z][A-Za-z\s/\-]+?\.--", stripped):
            break

        # Format A: multi-line tag (name on line 1, common name on line 2)
        lines = [clean_text(ln) for ln in raw.split("\n") if clean_text(ln)]
        if len(lines) >= 2:
            first = lines[0]
            second = lines[1]
            if re.match(r"^[A-Z][A-Z\s\-\.]+$", first) and len(first) >= 3:
                full_name = first
                if not re.match(r"^[A-Z\s\-]+$", second):
                    common_name = re.sub(r"\s*\([A-Z\-]+\)\s*$", "", second).strip()
                    common_name = common_name if common_name else None
                else:
                    common_name = None
                return full_name.strip(), common_name

        # Format B/C: single line
        if lines:
            single = lines[0]
            match = re.match(r"^([A-Z][A-Z\s\-\.]+?)\s+([A-Z][a-z].+)$", single)
            if match:
                full_name = match.group(1).strip()
                common_raw = match.group(2).strip()
                common_name = re.sub(r"\s*\([A-Z\-]+\)\s*$", "", common_raw).strip()
                return full_name, common_name if common_name else None

            if re.match(r"^[A-Z][A-Z\s\-\.]+$", single) and len(single) >= 3:
                return single.strip(), None

    return "", None


def _trim_to_general(
    pre_text: str,
    full_name: str,
    common_name: Optional[str],
) -> str:
    remainder = pre_text

    if full_name and full_name in pre_text:
        idx = pre_text.index(full_name) + len(full_name)
        remainder = pre_text[idx:].strip()

    if common_name and remainder.startswith(common_name):
        remainder = remainder[len(common_name):].strip()

    if not full_name or full_name not in pre_text:
        m = re.search(r"[A-Z][a-z]", remainder)
        if m:
            remainder = remainder[m.start():]

    remainder = re.sub(
        r"\s*Copyright\s*.*$", "", remainder, flags=re.IGNORECASE
    ).strip()

    return clean_text(remainder)


def _extract_general_and_sections(
    soup: BeautifulSoup,
    full_name: str,
    common_name: Optional[str],
) -> tuple[str, dict[str, str]]:
    blockquote = soup.find("blockquote") or soup
    bq_html = str(blockquote)

    parts = SECTION_SPLIT_RE.split(bq_html)

    pre_text = strip_html_tags(parts[0])
    general = _trim_to_general(pre_text, full_name, common_name)

    sections: dict[str, str] = {}
    for i in range(1, len(parts) - 1, 2):
        sec_name = clean_section_name(parts[i])
        sec_html = parts[i + 1] if (i + 1) < len(parts) else ""
        sec_text = strip_html_tags(sec_html)
        if sec_name and sec_text:
            sections[sec_name] = sec_text

    return general, sections


def _extract_relationships(sections: dict[str, str]) -> Optional[str]:
    for key in list(sections.keys()):
        if key.lower().startswith("relationship"):
            value = sections.pop(key)
            return value if value else None
    return None
# ----- #


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
    parser.add_argument("--letter", type=str, default=None)
    parser.add_argument("--delay",  type=float, default=None)
    parser.add_argument("--output", type=str, default=DEFAULT_OUTPUT)
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--mongo-uri", type=str, default="mongodb://localhost:27017/")
    args = parser.parse_args()

    letters_to_scrape = [args.letter.lower()] if args.letter else LETTERS

    all_remedies: list[dict] = load_existing_output(args.output)
    scraped_urls: set[str]   = {r["source_url"] for r in all_remedies}
    start_time               = datetime.now()

    for letter in letters_to_scrape:
        log.info(f"{'─' * 20} Letter {letter.upper()} {'─' * 20}")

        index_html = fetch_letter_index(letter)
        if index_html is None:
            log.error(f"Skipping letter '{letter.upper()}': index page failed.")
            continue

        remedy_links = parse_remedy_links(index_html, letter)
        if not remedy_links:
            continue

        total = len(remedy_links)
        count = 0

        for remedy in remedy_links:
            url    = remedy["url"]
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

    elapsed    = datetime.now() - start_time
    mins, secs = divmod(int(elapsed.total_seconds()), 60)

    print("\n" + "━" * 50)
    print("  Scrape Complete")
    print(f"  Total remedies scraped   : {len(all_remedies)}")
    print(f"  With common name         : {sum(1 for r in all_remedies if r.get('common_name'))}")
    print(f"  With relationships       : {sum(1 for r in all_remedies if r.get('relationships'))}")
    print(f"  Time taken               : {mins}m {secs}s")
    print(f"  Output saved to          : {args.output}")
    print("━" * 50 + "\n")


if __name__ == "__main__":
    main()    