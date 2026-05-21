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
