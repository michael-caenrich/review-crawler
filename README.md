# Review Crawler
Crawl and analyze e-commerce reviews to detect product safety risks.
This repository is the training version of the broader Recall Project.
It focuses on collecting product reviews from e-commerce platforms, standardizing the data,
and preparing it for downstream risk analysis (for example, identifying potential safety hazards
and negative product signals).

---

## Purpose of the Project
- Crawl product reviews from e-commerce platforms
- Filter for negative reviews to focus on risk signals
- Convert raw review text into a consistent analysis-ready format
- Support manual and automated labeling for risk-oriented tasks
- Provide a base for multi-platform crawling

---

## Current Scope
Implemented:
- AliExpress US ID collector — uses internal search API with subcategory iteration and manual cookie refresh
- AliExpress US review collector — async, uses internal review API with 1-star and 2-star filters, CDP cookie refresh, and concurrent product fetching
- CSV export with append-on-save and deduplication per product
- Hazard classification pipeline — two-stage LLM pipeline (pass 1: DeepSeek-V4-Flash, pass 2: stronger model validation (DeepSeek-V4-Pro))

Planned next:
- [x] Add AliExpress platform adapter
- [x] Add config-driven selectors, product IDs, and file paths
- [x] Add more product IDs per category via category page scraper
- [x] AliExpress US review crawler — replace Playwright with reverse-engineered API calls
- [x] AliExpress US ID collector — replace Playwright with reverse-engineered API calls
- [x] AliExpress US review crawler — migrate to async (`asyncio` + `httpx`) for parallel product collection
- [x] Hazard classification pipeline — two-stage LLM labeling with checkpoint resume and final Excel export

---

## Repository Structure
```text
.
├── crawlers/
│   └── aliexpress_us/
│       ├── collect_ids_aliexpress_us_api.py             # API-based ID collector (manual cookies)
│       ├── collect_reviews_aliexpress_us_api_async.py   # async API-based review collector (CDP)
│       └── fetch_categories_aliexpress_us_api.py        # fetch category tree from API
├── data/
│   └── aliexpress_us/
│       ├── aliexpress_us_categories.json                   # raw category tree from fetch script
│       ├── aliexpress_us_category_queries.json             # manually built subcategory → query mapping
│       ├── ids/
│       │   └── aliexpress_us_{category}_ids.json
│       └── reviews/
│           └── aliexpress_us_{category}_reviews_raw.csv
├── output/
│   └── aliexpress_us/
│       ├── labeled_csv/
│       │   ├── aliexpress_us_{category}_labeled.csv             # per-category checkpoint files
│       │   ├── aliexpress_us_hazard_reviews_classified.csv      # pass 1 output (DeepSeek-V4-Flash)
│       │   └── aliexpress_us_hazard_reviews_validated.csv       # pass 2 output (DeepSeek-V4-Pro)
│       └── aliexpress_us_hazard_reviews_final.xlsx              # union of pass 1 and pass 2
├── classify_reviews.py                                          # first-pass hazard classification (DeepSeek-V4-Flash)
├── validate_hazard_labels.py                                    # second-pass validation with stronger model (DeepSeek-V4-Pro)
├── config.py                                                    # paths, models, and prompts
└── cli_utils.py                                                 # shared utilities: output, LLM batch, cookies, API signing
```

---

## Crawling Notes

### Category setup (one-time, manual)
`fetch_categories_aliexpress_us_api.py` fetches the current AliExpress US category tree from the API
and writes it to `aliexpress_us_categories.json` (raw output, reference only).
`aliexpress_us_category_queries.json` is a manually built file that maps each subcategory to a search
query string — the ID collector reads directly from this file. Query strings affect which products
are returned and may need tuning to get accurate results.

### AliExpress US crawler — API (two-step workflow)

**Step 1 — Collect product IDs**
- Entry: `crawlers/aliexpress_us/collect_ids_aliexpress_us_api.py`
- Uses internal search API (`aliexpress.us/fn/search-pc/index`) — no token signing needed
- User picks a category; script auto-iterates all subcategories with pagination
- Cookies refreshed manually via `raw_cookies.txt` — no CDP required
- AliExpress blocks by IP after ~100 requests; script prompts to rotate VPN and resumes automatically
- Saves to `data/aliexpress_us/ids/aliexpress_us_{category}_ids.json`

**Step 2 — Collect reviews**
- Entry: `crawlers/aliexpress_us/collect_reviews_aliexpress_us_api_async.py`
- Uses internal review API (`mtop.aliexpress.review.pc.list`) with request signing (`md5(token&t&appKey&data)`)
- Collects 1-star and 2-star reviews with full pagination (50 reviews per page)
- Async — fetches multiple products concurrently (configurable via `CONCURRENCY`)
- Uses Chrome CDP to automatically refresh session token when it expires
- Interactive file picker — select category file at startup, supports running all files sequentially
- Saves to `data/aliexpress_us/reviews/aliexpress_us_{category}_reviews_raw.csv`

---

## Data Output Schema

### Raw reviews — `aliexpress_us_{category}_reviews_raw.csv`
| Column | Description |
|---|---|
| `product_id` | Platform product ID |
| `subcategory` | Subcategory the product was collected from |
| `review_text` | Raw review content (1-star and 2-star only) |

### First-pass output — `aliexpress_us_hazard_reviews_classified.csv`
| Column | Description |
|---|---|
| `product_id` | Platform product ID |
| `subcategory` | Subcategory the product was collected from |
| `review_text` | Raw review content |
| `hazard_label_classified` | 1 = hazard flagged by first pass, 0 = not |

### Validation output — `aliexpress_us_hazard_reviews_validated.csv`
| Column | Description |
|---|---|
| `product_id` | Platform product ID |
| `subcategory` | Subcategory the product was collected from |
| `review_text` | Raw review content |
| `hazard_label_classified` | Pass 1 label (DeepSeek-V4-Flash) |
| `hazard_label_validated` | Pass 2 label (DeepSeek-V4-Pro) |

### Final output — `aliexpress_us_hazard_reviews_final.xlsx`
| Column | Description |
|---|---|
| `product_id` | Platform product ID |
| `subcategory` | Subcategory the product was collected from |
| `review_text` | Raw review content |
| `hazard_label_classified` | Pass 1 label (DeepSeek-V4-Flash) |
| `hazard_label_validated` | Union of pass 1 and pass 2 (1 = confirmed hazard) |

---

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install pandas playwright colorama openpyxl requests httpx openai
```

Before running the AliExpress US review collector, launch Chrome with the debug port:
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 \
    --user-data-dir=$HOME/chrome-aliexpress-profile
```
Log into aliexpress.us in that window, then run the script.

---

## Run Crawlers
```bash
# AliExpress US — fetch category tree (one-time setup, then edit JSON manually)
python3 crawlers/aliexpress_us/fetch_categories_aliexpress_us_api.py

# AliExpress US — collect product IDs (requires raw_cookies.txt)
python3 crawlers/aliexpress_us/collect_ids_aliexpress_us_api.py

# AliExpress US — collect reviews async (requires Chrome with debug port)
python3 crawlers/aliexpress_us/collect_reviews_aliexpress_us_api_async.py
```

## Run Classification Pipeline
```bash
# Step 1 — first-pass classification (DeepSeek-V4-Flash, all reviews)
python3 classify_reviews.py

# Step 2 — second-pass validation with stronger model (DeepSeek-V4-Pro), merges both passes as union
python3 validate_hazard_labels.py
```

---

## Compliance and Safe Use
- This project is developed strictly for academic research purposes as part of a university study on e-commerce product safety
- Collected data is used solely for research analysis and is not redistributed or used commercially
- Respect platform Terms of Service and robots rules
- Do not collect private or sensitive personal information

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
