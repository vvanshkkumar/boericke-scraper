# Boericke's Homoeopathic Materia Medica — Web Scraper

A Python scraper that extracts all remedy data from [Boericke's Homoeopathic Materia Medica](http://homeoint.org/books/boericmm/index.htm) and outputs it as a clean, structured JSON file — built as part of a backend engineering internship assignment for **jarvis.care**.

---

## What This Project Does

The website has remedy pages for hundreds of homeopathic medicines organized A to Z. Each remedy page has a name, a general description, symptoms organized by organ system (like Head, Stomach, Fever), dosage info, and cross-references to related remedies.

This scraper:
- Visits all 26 letter index pages (a.htm through z.htm)
- Collects every remedy link from each letter
- Fetches each remedy page and extracts the content
- Saves everything as a single `boericke_remedies.json` file

The final output has **688 remedies** scraped across all 26 letters.

---

## Project Structure

```
boericke-scraper/
├── scraper.py               # Main scraper script
├── validator.py             # Validates the output JSON for quality
├── requirements.txt         # Python dependencies
├── README.md                # This file
├── boericke_remedies.json   # Pre-generated output (all A–Z remedies)
├── sample_output.json       # 5 remedies sample for quick review
├── failed_urls.txt          # Any URLs that failed (empty = all succeeded)
└── scraper.log              # Log file from the last full run
```

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/vvanshkkumar/boericke-scraper.git
cd boericke-scraper
```

### 2. Create a virtual environment (recommended)

```bash
python3 -m venv venv
source venv/bin/activate       # macOS/Linux
venv\Scripts\activate          # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Running the Scraper

> **Note before running:**
> **The repository already includes a fully pre-generated `boericke_remedies.json` file with all 688 remedies scraped across A–Z. If you want to run the scraper yourself from scratch, please delete or rename this file first — otherwise the scraper will see all URLs as already done and skip everything.**
>
> ```bash
> rm boericke_remedies.json   # macOS/Linux
> del boericke_remedies.json  # Windows
> ```

### Run for all letters (A–Z)

This is the full scrape. It took about **17 minutes 34 seconds** on my machine.

```bash
python3 scraper.py
```

### Run for a single letter only (recommended for testing first)

Before running the full scrape, it is a good idea to test with just one letter to make sure everything is working correctly:

```bash
python3 scraper.py --letter a
```

This will only scrape the A remedies (~101 remedies, takes about 2 minutes) and is much faster for checking if the output looks right.

### Other options

```bash
# Save output to a custom file
python3 scraper.py --output my_output.json

# Set a fixed delay between requests (default is random 0.5–1.0 seconds)
python3 scraper.py --delay 0.8

# Combine options
python3 scraper.py --letter c --output letter_c.json
```

### Progress output

While running you will see something like this in the terminal:

```
[A] Scraped 1/101 - ABIES CANADENSIS-PINUS CANADENSIS
[A] Scraped 2/101 - ABIES NIGRA
[A] Scraped 3/101 - ABRUS PRECATORIUS -- JEQUIRITY
...
```

---

## What the Output Looks Like

Each remedy in `boericke_remedies.json` follows this schema:

```json
{
  "abbreviation": "ABIES-C",
  "full_name": "ABIES CANADENSIS-PINUS CANADENSIS",
  "common_name": "Hemlock Spruce",
  "source_url": "http://homeoint.org/books/boericmm/a/abies-c.htm",
  "letter": "A",
  "general": "Mucous membranes are affected by Abies can and gastric symptoms are most marked...",
  "sections": {
    "Head": "Feels light-headed, tipsy. Irritable.",
    "Stomach": "Canine hunger with torpid liver. Gnawing, hungry, faint feeling...",
    "Female": "Uterine displacements. Sore feeling at fundus of uterus...",
    "Fever": "Cold shivering, as if blood were ice-water...",
    "Dose": "First to third potency."
  },
  "relationships": null,
  "potencies": ["1", "3"],
  "keywords": ["stomach", "cold", "mucous", "membranes", "uterine", ...]
}
```

### Final stats from my run

| Letter | Remedies |
|--------|----------|
| A | 101 |
| B | 30 |
| C | 108 |
| D | 11 |
| E | 23 |
| F | 19 |
| G | 23 |
| H | 22 |
| I | 15 |
| J | 10 |
| K | 18 |
| L | 32 |
| M | 41 |
| N | 20 |
| O | 21 |
| P | 42 |
| Q | 4 |
| R | 18 |
| S | 64 |
| T | 33 |
| U | 7 |
| V | 16 |
| W | 1 |
| X | 3 |
| Y | 2 |
| Z | 4 |
| **Total** | **688** |

- Remedies with common name: **679 / 688**
- Remedies with relationships: **540 / 688**
- Remedies with potencies extracted: **611 / 688**
- Remedies with keywords: **688 / 688**

---

## Terminal Screenshot (Full A–Z Run)

The screenshot below shows the scraper completing the full A–Z run on my machine:

![Terminal Run](screenshot_terminal_run.png)

---

## Bonus Features (Beyond the Assignment)

The assignment had three optional bonus tasks. I implemented all three.

### 1. Potencies extraction

The `Dose` section of each remedy contains text like *"First to third potency"* or *"Third to thirtieth potency"*. The scraper parses both numeric formats (like `30c`, `6x`) and written-out ordinal words (like `"third"` → `"3"`, `"thirtieth"` → `"30"`) and stores them as a list in the `potencies` field.

### 2. Keyword extraction

For each remedy, the scraper takes all the text from `general` + all `sections` combined, strips common stopwords, and finds the top 10 most frequently occurring meaningful words. These are stored in the `keywords` field and can be useful for search and filtering in the AI application.

### 3. MongoDB upload

You can push the scraped data directly into a local MongoDB collection using the `--upload` flag.

**Make sure MongoDB is running locally first:**

```bash
# macOS (with Homebrew)
brew services start mongodb-community

# Linux
sudo systemctl start mongod
```

**Then run the scraper with upload:**

```bash
python3 scraper.py --upload
```

Or if your MongoDB is running on a different URI:

```bash
python3 scraper.py --upload --mongo-uri "mongodb://localhost:27017/"
```

This will:
- Scrape all remedies (or load from existing JSON)
- Connect to MongoDB at `localhost:27017`
- Create a database called `jarvis` with a collection called `remedies`
- Insert all 688 remedy documents

After running, you can verify in the MongoDB shell:

```bash
mongosh
use jarvis
db.remedies.countDocuments()   # Should return 688
db.remedies.findOne({ abbreviation: "ACON" })
```

---

## Extra Things I Added (Not in the Assignment)

These two files were not required by the assignment, but I added them because they genuinely helped me build and verify the scraper correctly.

### `scraper.log` — Logging

The scraper writes a log file to `scraper.log` while it runs. The console only shows INFO-level messages (letter progress), but the log file also captures DEBUG messages like individual retry attempts and HTTP errors — useful when something goes wrong.

This is what the log file looks like after a full run:

```
09:16:18 [INFO   ] ──────────────── Letter A ────────────────
09:18:14 [INFO   ] Letter A done. 101/101 remedies saved.
09:18:14 [INFO   ] ──────────────── Letter B ────────────────
09:18:58 [INFO   ] Letter B done. 60/60 remedies saved.
...
09:33:52 [INFO   ] Letter Z done. 8/8 remedies saved.
```

I added logging because without it, if the scraper crashed halfway through a long run, I had no idea where it failed or why.

### `validator.py` — Output Quality Checker

After scraping, I was not sure if the output was actually clean or if there was still some website boilerplate text leaking into the data. So I wrote a validator script that checks every single remedy in the JSON for:

- Missing required fields
- Boilerplate text like "William BOERICKE" or "Copyright" leaking into `general` or `sections`
- Section names that are too long (which would mean the regex failed and captured a sentence instead of a heading)
- Section content that is suspiciously short
- URL mismatches between the abbreviation and source URL

**To run it:**

```bash
python3 validator.py
```

The validator screenshot below shows the result from my final run — **0 errors**, and only 2 minor warnings (both are known edge cases where the site itself uses a slightly different filename from the abbreviation — not a scraper bug):

![Validator Output](screenshot_validator.png)

I added the validator because during development I kept second-guessing whether the parser was working correctly. Having a script that checked 688 entries automatically and gave me a clean report was much better than manually spot-checking a handful of entries.

---

## How the Scraper Works (Code Walkthrough)

The scraper is broken into clean modular functions as required. Here is what each major function does:

### `fetch_letter_index(letter)`
Fetches the index page for a letter (e.g. `a.htm`) which lists all the remedies under that letter as links.

### `parse_remedy_links(html, letter)`
Parses the letter index page and extracts every remedy abbreviation + URL pair. The links sit inside a `<blockquote>` tag as `<a>` elements.

### `fetch_with_retry(url)`
All HTTP requests go through this function. It tries up to 3 times with exponential backoff (2s, 4s, 8s) before giving up. If a page fails all retries, the URL gets logged to `failed_urls.txt`.

### `_extract_names(soup)`
Pulls the full Latin name from the page `<title>` tag (the most reliable place on the site), and finds the common name from the inline text next to the decorative font element in the page header.

### `_extract_general_and_sections(soup, full_name, common_name)`
This is the core parsing function. It:
1. Gets all the text from the page and splits it line by line
2. Filters out navigation links, boilerplate header text, and copyright notices
3. Splits the remaining text on section headers like `Head.--`, `Stomach.--`, etc.
4. Everything before the first section header becomes `general`
5. Everything after each header (until the next one) becomes that section's content

### `_extract_relationships(sections)`
If a section called `Relationships` (or similar) was found, this pops it out of the sections dict and returns it as its own field.

### `extract_potencies(dose_text)`
Parses the Dose section text to extract potency values. Handles both `30c`/`6x` style numeric formats and written ordinals like `"third"` or `"thirtieth"`.

### `extract_keywords(text)`
Simple word frequency counter on the combined text of a remedy, after removing stopwords. Returns the top 10 words.

### `save_output(remedies, filepath)` and `load_existing_output(filepath)`
The scraper is resumable — on startup it loads any existing JSON, builds a set of already-scraped URLs, and skips those during the run. This means if it crashes at letter M, you can just re-run it and it picks up from where it left off.

---

## Resumable Scraping

The scraper checks `boericke_remedies.json` on every run and skips any URL that was already scraped. This means:

- If it crashes mid-run, just run it again — no data is lost and it continues from where it stopped
- If you already scraped A and want to add B, just run `python3 scraper.py --letter b` and it will append to the existing file

---

## Dependencies

```
beautifulsoup4==4.14.3
requests==2.34.2
lxml==6.1.1
pymongo==4.6.1       # only needed for --upload flag
```

Install everything with:

```bash
pip install -r requirements.txt
```

---

## Notes

- The scraper adds a random 0.5–1.0 second delay between requests by default so it does not hammer the server
- All failed URLs are saved to `failed_urls.txt` — in my full run this file was completely empty (zero failures)
- The scraper uses `html.parser` (Python's built-in) rather than `lxml` for parsing individual remedy pages, because `lxml` was mishandling the old nested HTML structure of this 1999-era website
- Page encoding is forced to `latin-1` since the site pre-dates UTF-8

---

*Built by Vansh Kumar — jarvis.care Backend Internship Assignment*
