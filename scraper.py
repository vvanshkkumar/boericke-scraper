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