# Review Crawler
Crawl and analyze e-commerce reviews to detect product safety risks.
This repository is the training version of the broader Recall Project. 
It focuses on collecting product reviews from e-commerce platforms, standardizing the data, 
and preparing it for downstream risk analysis (for example, identifying potential safety hazards 
and negative product signals).

---

## Purpose of the Project
- Crawl product reviews from e-commerce platforms
- Convert raw review text into a consistent analysis-ready format
- Support manual labeling for risk-oriented tasks
- Provide a base for multi-platform crawling, not only JD

---

## Current Scope
Implemented now:
- JD API-based crawling
- JD browser-assisted crawling using Playwright + Chrome CDP
- Excel export with placeholder labeling columns

Planned next:
- Add more platform adapters (for example, Amazon, Taobao/Tmall, and others)
- Unify crawler interface and output schema
- Add config-driven crawl jobs and better retry/logging

---

## Repository Structure
```text
.
├── crawlers/
│   ├── collect_reviews.py
│   ├── collect_reviews_jd_claude.py
│   ├── collect_reviews_jd_gpt.py
│   └── ... future platform crawlers
├── data/
│   └── reviews_raw.xlsx
├── output/
├── notebooks/
├── src/
├── config.py
└── cli_utils.py
```

---

## Crawling Notes

### JD API crawler
- Entry: `crawlers/collect_reviews.py`
- Uses JD comment API endpoints
- Best for lightweight batch collection when endpoints remain accessible

### JD Playwright crawler
- Entry: `crawlers/collect_reviews_jd_claude.py` and `crawlers/collect_reviews_jd_gpt.py`
- Connects to Chrome via CDP (`http://127.0.0.1:9222`)
- Useful when dynamic page rendering or login/session state is required

---

## Data Output Schema (raw)
Typical output columns:
- `product_id` or `product_url`
- `review` or `review_text`
- `rating` (if available)
- `is_negative` (manual label placeholder)
- `hazard_label` (manual label placeholder)

Default output path: \
`data/reviews_raw.xlsx`

---

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install pandas requests playwright colorama openpyxl
playwright install chromium
```

---

## Run Crawlers
```bash
python3 crawlers/collect_reviews.py
python3 crawlers/collect_reviews_jd_claude.py
python3 crawlers/collect_reviews_jd_gpt.py
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

