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
