"""Store input, output file paths, negative keywords, selectors, product IDs for JD and Taobao platforms."""

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
4. Press Enter to continue.
"""

BASE_DIR = pathlib.Path(__file__).resolve().parent

NEGATIVE_KEYWORDS = [
    # Safety hazards
    "皮肤刺激", "眼睛刺激", "过敏", "疙瘩", "痘", "受伤", "发烫", "危险", "刺鼻",
    # Product defects
    "假货", "破损", "坏了", "少配件", "空的", "二手", "没有电池",
    # Quality
    "质量差", "质量一般", "垃圾", "廉价", "不推荐",
    # Usability
    "不好用", "难用", "充不满", "不好",
    # Returns & service
    "退货", "退款", "失望",
]

NEGATIVE_KEYWORDS_EN = [
    # Safety hazards
    "irritat", "allerg", "rash", "burn", "dangerous", "hazard", "toxic", "chok",
    # Product defects
    "fake", "broken", "damaged", "missing", "empty", "defect", "counterfeit",
    # Quality
    "poor quality", "bad quality", "cheap", "garbage", "trash", "terrible", "worst",
    # Usability
    "doesn't work", "does not work", "not working", "useless", "difficult to use",
    # Returns & service
    "refund", "return", "disappointed", "scam", "waste of money",
]

# AliExpress setup
ALIEXPRESS_URL = "https://www.aliexpress.com"

ALIEXPRESS_IDS_CATEGORY = "toys_games"  # update when switching categories
ALIEXPRESS_DATA_PATH = BASE_DIR / "data" / "aliexpress_us"
ALIEXPRESS_REVIEWS_PATH = ALIEXPRESS_DATA_PATH / f"aliexpress_us_{ALIEXPRESS_IDS_CATEGORY}_reviews_raw.xlsx"
ALIEXPRESS_OUTPUT_PATH = BASE_DIR / "output" / "aliexpress_us_results.xlsx"
COOKIES_PATH = ALIEXPRESS_DATA_PATH / "aliexpress_us_api_cookies.json"

ALIEXPRESS_SELECTORS = {
    "category": "[href*='categoryTab']",
    "product_link": "a[href*='/item/']",
    "view_more": "#nav-review button[class*=v3--btn]",
    "ratings_dropdown": ".comet-v2-modal-content [class*=filterItem]:first-child button",
    "1_star": "li:has-text('1 Star')",
    "2_star": "li:has-text('2 Star')",
    "review_container": ".comet-v2-modal-content [class*=itemContent]",
    "review_text": ".comet-v2-modal-content [class*=itemReview]",
    "rating": "a[class*='reviewer--rating'] strong",
    "reviews": "a[class*='reviewer--reviews']",
    "captcha": ["#captcha", "[class*='rc-anchor']", "iframe[src*='recaptcha']"],
}

ALIEXPRESS_CATEGORIES_US = json.loads(
    (ALIEXPRESS_DATA_PATH / "aliexpress_us_category_queries.json").read_text()
)