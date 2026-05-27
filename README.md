# Review Crawler
Crawl and analyze e-commerce reviews to detect product safety risks.
This repository is the training version of the broader Recall Project.
It focuses on collecting product reviews from e-commerce platforms, standardizing the data,
and preparing it for downstream risk analysis (for example, identifying potential safety hazards
and negative product signals).

---

## Purpose of the Project
- Crawl product reviews from e-commerce platforms
- Filter for negative reviews (差评) to focus on risk signals
- Convert raw review text into a consistent analysis-ready format
- Support manual labeling for risk-oriented tasks
- Provide a base for multi-platform crawling, not only JD

---

## Current Scope
Implemented now:
- JD Playwright crawler with auto-click of 全部评价, 差评 and 中评 filters
- Taobao Playwright crawler with auto-click of 查看全部评价
- AliExpress Playwright crawler with 1-star and 2-star filter support
- AliExpress US category ID collector — scrapes product IDs from any category page
- AliExpress US review crawler — reads IDs from JSON, skips high-rated products, detects captcha
- Keyword-based `is_negative` auto-labeling using configurable keyword lists (Chinese and English)
- Excel export with append-on-save and deduplication per product
- Placeholder labeling columns for manual annotation

Planned next:
- [x] Add Taobao platform adapter
- [x] Add AliExpress platform adapter
- [x] Unify crawler interface and output schema
- [x] Add config-driven selectors, product IDs, and file paths
- [x] Improve scroll to load more reviews per product
- [x] Improve anti-bot detection (random delays, human-like scroll pauses)
- [x] Add more product IDs per category via category page scraper
- [ ] AliExpress US review crawler — replace Playwright with reverse-engineered API calls
- [ ] AliExpress US ID collector — replace Playwright with reverse-engineered API calls

---

## Repository Structure
```text
.
├── crawlers/
│   ├── aliexpress_us/
│   │   ├── collect_ids_aliexpress_us.py     # scrapes product IDs from a category page
│   │   └── collect_reviews_aliexpress_us.py # collects reviews from IDs JSON
│   ├── collect_reviews_jd.py
│   ├── collect_reviews_taobao.py
│   └── collect_reviews_aliexpress.py
├── data/
│   ├── aliexpress_us/
│   │   ├── aliexpress_us_{category}_{count}_ids.json
│   │   └── aliexpress_us_{category}_reviews_raw.xlsx
│   ├── jd_reviews_raw.xlsx
│   └── taobao_reviews_raw.xlsx
├── output/
├── config.py                       # selectors, keywords, file paths
└── cli_utils.py
```

---

## Crawling Notes

### JD Playwright crawler
- Entry: `crawlers/collect_reviews_jd.py`
- Connects to your real Chrome via CDP (`http://127.0.0.1:9222`)
- Auto-clicks '全部评价' to open the reviews popup
- Auto-clicks 差评 and '中评' filters to collect negative reviews
- Falls back to manual click with prompt if auto-click fails
- Scrolls all available reviews per filter with human-like pauses

### Taobao Playwright crawler
- Entry: `crawlers/collect_reviews_taobao.py`
- Connects to your real Chrome via CDP (`http://127.0.0.1:9222`)
- Auto-clicks '查看全部评价' to open the reviews popup
- No negative filter available — relies on keyword-based `is_negative` labeling
- Falls back to manual click with prompt if auto-click fails

### AliExpress Playwright crawler
- Entry: `crawlers/collect_reviews_aliexpress.py`
- Connects to your real Chrome via CDP (`http://127.0.0.1:9222`)
- Auto-clicks 'View more' to open the reviews popup
- Auto-clicks 1-star and 2-star filters to collect negative reviews
- Falls back to manual click with prompt if 'View more' auto-click fails
- Skips a star filter silently if no reviews load after clicking

### AliExpress US crawler (two-step workflow)

**Step 1 — Collect product IDs**
- Entry: `crawlers/aliexpress_us/collect_ids_aliexpress_us.py`
- Opens AliExpress homepage, lists categories, user picks one
- Scrolls category page to load products with human-like pauses
- If IDs file for this category already exists, merges new IDs and saves with updated count
- Saves IDs to `data/aliexpress_us/aliexpress_us_{category}_{count}_ids.json`

**Step 2 — Collect reviews**
- Entry: `crawlers/aliexpress_us/collect_reviews_aliexpress_us.py`
- Reads IDs from the JSON produced in step 1
- Skips products with rating ≥ 4.8 or fewer than 10 reviews
- Detects captcha, plays alert sound, saves progress, waits for manual solve
- Batch-saves every 5 products to prevent data loss
- Pauses every 100 products for a manual break

---

## Data Output Schema (raw)
Typical output columns:
- `product_id` — platform product ID
- `review_text` — raw review content
- `is_negative` — auto-filled via keyword matching (`1` = negative signal, `0` = no match); manual verification recommended
- `hazard_label` — manual label placeholder for hazard type

Output paths:
- `data/jd_reviews_raw.xlsx`
- `data/taobao_reviews_raw.xlsx`
- `data/aliexpress_reviews_raw.xlsx`
- `data/aliexpress_us/aliexpress_us_{category}_reviews_raw.xlsx`

---

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install pandas playwright colorama openpyxl
```

Before running the JD Playwright crawler, launch Chrome with the debug port:
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 \
    --user-data-dir=$HOME/chrome-jd-profile
```
Log into JD.com in that window, then run the script.

Before running the Taobao Playwright crawler, launch Chrome with the debug port:
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 \
    --user-data-dir=$HOME/chrome-taobao-profile
```
Log into Taobao.com in that window, then run the script.

Before running the AliExpress Playwright crawler, launch Chrome with the debug port:
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 \
    --user-data-dir=$HOME/chrome-aliexpress-profile
```
Log into AliExpress.com in that window, then run the script.

---

## Run Crawlers
```bash
# JD Playwright crawler (requires Chrome with debug port — see Local Setup)
python3 crawlers/collect_reviews_jd.py

# Taobao Playwright crawler (requires Chrome with debug port — see Local Setup)
python3 crawlers/collect_reviews_taobao.py

# AliExpress Playwright crawler (requires Chrome with debug port — see Local Setup)
python3 crawlers/collect_reviews_aliexpress.py
```

---

## Compliance and Safe Use
- Respect platform Terms of Service and robots rules
- Avoid abusive request frequencies
- Do not collect private or sensitive personal information
- Use collected data only for legitimate research/training purposes

---

## Training Version Note
This repository is intentionally focused on crawler and risk-analysis data preparation workflows.
It may contain experimental scripts and should be treated as a training branch of the full system.

---

## License
[MIT License](LICENSE)

---

## Author
**Pavel Kandrichin**
GitHub: [michael-caenrich](https://github.com/michael-caenrich)