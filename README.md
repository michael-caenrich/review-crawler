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
- JD API-based crawling
- JD browser-assisted crawling using Playwright + Chrome CDP
- Auto-click of 全部评价 and 差评 filter
- Excel export with append-on-save (no overwriting between runs)
- Placeholder labeling columns for manual annotation

Planned next:
- Add more platform adapters (for example, Amazon, Taobao/Tmall, and others)
- Unify crawler interface and output schema
- Add config-driven crawl jobs and better retry/logging
- Auto-detect product category from page title

---

## Repository Structure
```text
.
├── crawlers/
│   ├── collect_reviews.py          # JD API crawler
│   ├── collect_reviews_jd.py       # JD Playwright crawler (main)
│   └── ... future platform crawlers
├── data/
│   └── reviews_raw.xlsx
├── output/
├── notebooks/
├── src/
├── config.py                       # product IDs, selectors, file paths
└── cli_utils.py
```

---

## Crawling Notes

### JD API crawler
- Entry: `crawlers/collect_reviews.py`
- Uses JD comment API endpoints
- Best for lightweight batch collection when endpoints remain accessible

### JD Playwright crawler
- Entry: `crawlers/collect_reviews_jd.py`
- Connects to your real Chrome via CDP (`http://127.0.0.1:9222`)
- Auto-clicks 全部评价 to open the reviews popup
- Auto-clicks 差评 to filter for negative reviews only
- Falls back to manual click with prompt if auto-click fails
- Useful when dynamic page rendering or login/session state is required

---

## Data Output Schema (raw)
Typical output columns:
- `product_id` — JD product ID
- `review_text` — raw review content
- `is_negative` — pre-filled with `1` for 差评 reviews (manual verification recommended)
- `hazard_label` — manual label placeholder for hazard type

Default output path:
`data/reviews_raw.xlsx`

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

---

## Run Crawlers
```bash
# JD API crawler
python3 crawlers/collect_reviews.py

# JD Playwright crawler (requires Chrome with debug port — see Local Setup)
python3 crawlers/collect_reviews_jd.py
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
