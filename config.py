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

ALIEXPRESS_DATA_PATH = BASE_DIR / "data" / "aliexpress_us"
ALIEXPRESS_IDS_PATH = ALIEXPRESS_DATA_PATH / "ids"
ALIEXPRESS_REVIEWS_PATH = ALIEXPRESS_DATA_PATH / "reviews"
ALIEXPRESS_OUTPUT_PATH = BASE_DIR / "output" / "aliexpress_us"
ALIEXPRESS_LABELED_PATH =  ALIEXPRESS_OUTPUT_PATH / "labeled_csv"
COOKIES_PATH = ALIEXPRESS_DATA_PATH / "aliexpress_us_api_cookies.json"

ALIEXPRESS_CATEGORIES_US = json.loads(
    (ALIEXPRESS_DATA_PATH / "aliexpress_us_category_queries.json").read_text()
)

MODELS = {
    "DeepInfra": {
        "DeepSeek-V4-Flash": "deepseek-ai/DeepSeek-V4-Flash",  # 284B ($0.10 in, $0.02 cached, $0.20 out / 1M)
        "DeepSeek-V4-Pro": "deepseek-ai/DeepSeek-V4-Pro",      # 1.6T ($1.30 in, $0.10 cached, $2.60 out / 1M)
        "base_url": "https://api.deepinfra.com/v1/openai",
    },
    "OpenAI API": {
        "gpt-5.1": "gpt-5.1",            # Standard ($1.25 in, $0.125 cached, $10.00 out / 1M)
        "gpt-4.1": "gpt-4.1",
        "gpt-4.1-mini": "gpt-4.1-mini",
        "gpt-4o-mini": "gpt-4o-mini",
    }
}

PROMPT_HAZARD = """Classify each product review. Return a JSON array only.

    Return 1 if the review clearly describes:
    - personal injury: pain, bleeding, rash, allergy, swelling, poisoning
    - choking hazard (small parts for children)
    - electric shock, short circuit, sparks, smoke, fire, explosion, or burning
    - device or charger dangerously hot to the touch
    - product melting or deforming in a way that causes smoke, fire, or burn risk — not just product failure
    - chemical/toxic smell causing physical symptoms (headache, nausea, throat pain, eye irritation)
    - product unsafe for food contact
    - wrong voltage causing component failure or fire
    - product bursting or rupturing during normal use

    Return 0 if the review only describes:
    - broken, poor quality, wrong or fake product, stopped working
    - property damage (printer, phone, car) without personal injury
    - leaking, refund issue, seller problem
    - discomfort from poor fit or normal use
    - fraud, scam, misleading listing, or malware/software issues
    - product getting warm during normal use
    - phone or device overheating without fire, burn, or smoke
    - product melted or warped by heat without fire or smoke
    - bad or unpleasant odor without toxic concern

    If unclear, choose 0.

    Output example:
    [0, 1, 0, 0, 1]"""
