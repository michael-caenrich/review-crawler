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
- AliExpress US ID collector — uses internal search API with automatic subcategory iteration and CDP cookie refresh
- AliExpress US review crawler — uses internal review API with 1-star and 2-star filters, pagination, and CDP cookie refresh
- Keyword-based `is_negative` auto-labeling for JD and Taobao using configurable keyword lists (Chinese and English)
- Excel export with append-on-save and deduplication per product
- Placeholder `hazard_label` column for manual annotation

Planned next:
- [x] Add Taobao platform adapter
- [x] Add AliExpress platform adapter
- [x] Unify crawler interface and output schema
- [x] Add config-driven selectors, product IDs, and file paths
- [x] Improve scroll to load more reviews per product
- [x] Improve anti-bot detection (random delays, human-like scroll pauses)
- [x] Add more product IDs per category via category page scraper
- [x] AliExpress US review crawler — replace Playwright with reverse-engineered API calls
- [x] AliExpress US ID collector — replace Playwright with reverse-engineered API calls
- [ ] AliExpress US review crawler — migrate internal API calls to async (`asyncio` + `aiohttp`) for parallel product collection
- [ ] AliExpress US ID collector — migrate internal API calls to async (`asyncio` + `aiohttp`) for parallel subcategory collection

---

## Repository Structure
```text
.
├── crawlers/
│   ├── aliexpress_us/
│   │   ├── collect_ids_aliexpress_us.py        # Playwright-based ID collector (legacy)
│   │   ├── collect_ids_aliexpress_us_api.py    # internal API-based ID collector
│   │   ├── collect_reviews_aliexpress_us.py    # Playwright-based review crawler (legacy)
│   │   └── collect_reviews_aliexpress_us_api.py# internal API-based review crawler
│   ├── collect_reviews_jd.py
│   ├── collect_reviews_taobao.py
│   └── collect_reviews_aliexpress.py
├── data/
│   ├── aliexpress_us/
│   │   ├── aliexpress_us_{category}_ids.json
│   │   └── aliexpress_us_{category}_reviews_raw.xlsx
│   ├── jd_reviews_raw.xlsx
│   └── taobao_reviews_raw.xlsx
├── output/
├── config.py                                   # selectors, keywords, file paths
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

### AliExpress US crawler — API (two-step workflow, recommended)

**Step 1 — Collect product IDs**
- Entry: `crawlers/aliexpress_us/collect_ids_aliexpress_us_api.py`
- Uses internal search API (`aliexpress.us/fn/search-pc/index`) — no token signing needed
- User picks a category; script auto-iterates all subcategories with pagination (60+ pages each)
- Stores each entry with `id` and `subcategory` fields
- Uses Chrome CDP to automatically refresh cookies on bot detection or auth errors
- Saves IDs to `data/aliexpress_us/aliexpress_us_{category}_ids.json`

**Step 2 — Collect reviews**
- Entry: `crawlers/aliexpress_us/collect_reviews_aliexpress_us_api.py`
- Uses internal review API (`mtop.aliexpress.review.pc.list`) with request signing (`md5(token&t&appKey&data)`)
- Collects 1-star and 2-star reviews with full pagination (50 reviews per page)
- Uses Chrome CDP to automatically refresh session token when it expires (~30 min)
- Batch-saves every 500 products; pauses 60–120s every 100 products

### AliExpress US crawler — Playwright (legacy)

**Step 1 — Collect product IDs**
- Entry: `crawlers/aliexpress_us/collect_ids_aliexpress_us.py`
- Opens AliExpress homepage via CDP, lists categories, user picks one
- Scrolls category page to load products with human-like pauses

**Step 2 — Collect reviews**
- Entry: `crawlers/aliexpress_us/collect_reviews_aliexpress_us.py`
- Reads IDs from JSON, clicks 1-star and 2-star filters in browser
- Detects captcha, plays alert sound, waits for manual solve

---

## Data Output Schema (raw)
JD and Taobao output columns:
- `product_id` — platform product ID
- `review_text` — raw review content
- `is_negative` — auto-filled via keyword matching (`1` = negative signal, `0` = no match); manual verification recommended
- `hazard_label` — manual label placeholder for hazard type

AliExpress US output columns:
- `product_id` — platform product ID
- `subcategory` — subcategory the product was collected from
- `review_text` — raw review content (1-star and 2-star only — all reviews are negative by construction)
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
pip install pandas playwright colorama openpyxl requests
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

# AliExpress US — collect product IDs via internal API (requires Chrome with debug port)
python3 crawlers/aliexpress_us/collect_ids_aliexpress_us_api.py

# AliExpress US — collect reviews via internal API (requires Chrome with debug port)
python3 crawlers/aliexpress_us/collect_reviews_aliexpress_us_api.py
```

---

## Compliance and Safe Use
- This project is developed strictly for academic research purposes as part of a university study on e-commerce product safety
- Collected data is used solely for research analysis and is not redistributed or used commercially
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