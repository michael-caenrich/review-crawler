"""Paths, credentials, and shared configuration for AliExpress US crawlers."""

import json
import pathlib

CDP_URL = "http://127.0.0.1:9222"

CDP_INSTRUCTION = """
1. Quit Chrome completely.
2. Reopen Chrome with a dedicated debug profile:
   /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\
       --remote-debugging-port=9222 \\
       --user-data-dir=$HOME/chrome-aliexpress-profile
3. Log into AliExpress.com in that Chrome window if not logged in yet.
4. Press Enter to continue."""

BASE_DIR = pathlib.Path(__file__).resolve().parent

ALIEXPRESS_URL = "https://www.aliexpress.com"

ALIEXPRESS_IDS_CATEGORY = "appliances"  # update when switching categories
ALIEXPRESS_DATA_PATH = BASE_DIR / "data" / "aliexpress_us"
ALIEXPRESS_IDS_PATH = ALIEXPRESS_DATA_PATH / "ids"
ALIEXPRESS_REVIEWS_PATH = ALIEXPRESS_DATA_PATH / "reviews" / f"aliexpress_us_{ALIEXPRESS_IDS_CATEGORY}_reviews_raw.xlsx"
COOKIES_PATH = ALIEXPRESS_DATA_PATH / "aliexpress_us_api_cookies.json"

ALIEXPRESS_CATEGORIES_US = json.loads(
    (ALIEXPRESS_DATA_PATH / "aliexpress_us_category_queries.json").read_text()
)