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
- Keyword-based `is_negative` auto-labeling using configurable keyword lists (Chinese and English)
- Excel export with append-on-save and deduplication per product
- Placeholder labeling columns for manual annotation

Planned next:
- [x] Add Taobao platform adapter
- [x] Add AliExpress platform adapter
- [x] Unify crawler interface and output schema
- [x] Add config-driven selectors, product IDs, and file paths
- [x] Improve scroll to load more reviews per product
- [ ] Add Bright Data Browser API adapter for cloud-based scraping
- [ ] Auto-detect product category from page title
- [ ] Improve anti-bot detection (random delays, user-agent rotation)
- [ ] Add more product IDs per category
- [ ] Add retry/logging for failed products

---

## Repository Structure
```text
.
├── crawlers/
│   ├── collect_reviews_jd.py           # JD Playwright crawler
│   ├── collect_reviews_taobao.py       # Taobao Playwright crawler
│   └── collect_reviews_aliexpress.py   # AliExpress Playwright crawler
├── data/
│   ├── jd_reviews_raw.xlsx
│   ├── taobao_reviews_raw.xlsx
│   └── aliexpress_reviews_raw.xlsx
├── output/
│   ├── jd_results.xlsx
│   ├── taobao_results.xlsx
│   └── aliexpress_results.xlsx
├── notebooks/
├── src/
├── config.py                       # product IDs, selectors, keywords, file paths
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
- Collects up to `SCROLL_ROUNDS` pages of reviews per filter

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