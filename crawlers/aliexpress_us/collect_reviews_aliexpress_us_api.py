"""
Collect 1-star and 2-star reviews from AliExpress via internal review API.
Uses Chrome CDP to automate cookie refreshment when the session token expires.

Before running:
    1. Quit Chrome completely.
    2. Reopen Chrome with a dedicated debug profile:
       /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \
           --remote-debugging-port=9222 \
           --user-data-dir=$HOME/chrome-aliexpress-profile
    3. Log into AliExpress in that Chrome window.
    4. Run this script.
"""

import json
import re
import sys
import time
import random
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import requests
import pandas as pd
from playwright.sync_api import sync_playwright

from cli_utils import colorize, play_alert_sound, get_token, generate_sign, find_ids_file, refresh_cookies_cdp, TokenExpiredError
from config import ALIEXPRESS_DATA_PATH, ALIEXPRESS_IDS_CATEGORY, ALIEXPRESS_REVIEWS_PATH, ALIEXPRESS_URL, CDP_URL, CDP_INSTRUCTION

APP_KEY = "12574478"
API_URL = "https://acs.aliexpress.us/h5/mtop.aliexpress.review.pc.list/1.0/"

HEADERS = {
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "referer": "https://www.aliexpress.us/",
    "sec-fetch-dest": "script",
    "sec-fetch-mode": "no-cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
}

PAGE_SIZE = 50


def fetch_page(session: requests.Session, product_id: str, page: int, star: str) -> dict | None:
    """Make one API request and return the parsed JSON response, or None on failure."""
    t = str(int(time.time() * 1000))
    data = {
        "productId": str(product_id),
        "page": page,
        "pageSize": PAGE_SIZE,
        "_lang": "en_US",
        "filter": star,
        "sort": "complex_default",
        "country": "US",
        "clientType": "web",
    }
    data_str = json.dumps(data, separators=(",", ":"))
    sign = generate_sign(get_token(session), t, APP_KEY, data_str)

    params = {
        "jsv": "2.5.1",
        "appKey": APP_KEY,
        "t": t,
        "sign": sign,
        "api": "mtop.aliexpress.review.pc.list",
        "v": "1.0",
        "type": "jsonp",
        "dataType": "jsonp",
        "callback": "mtopjsonp1",
        "data": data_str,
    }

    try:
        resp = session.get(API_URL, params=params, headers=HEADERS, timeout=15)
        match = re.search(r"mtopjsonp\d+\((.+)\)$", resp.text)
        if not match:
            print(f"{colorize('[WARNING]')} Unexpected response: {resp.text[:200]}")
            return None
        return json.loads(match.group(1))
    except Exception as e:
        print(f"{colorize('[WARNING]')} Request failed: {e}")
        return None


def parse_reviews(data: dict, product_id: str, subcategory: str = "") -> tuple[list[dict], int]:
    """Extract review texts and total page count from an API response."""
    result = data.get("data") or {}
    review_list = (
        result.get("reviewList")
        or result.get("reviews")
        or result.get("evaViewList")
        or []
    )

    reviews = []
    for r in review_list:
        text = (
            r.get("reviewContent")
            or r.get("content")
            or r.get("buyerFeedback")
            or ""
        ).strip()
        if text:
            reviews.append({"product_id": product_id, "subcategory": subcategory, "review_text": text})

    total_pages = int(result.get("totalPage") or result.get("maxPage") or 1)
    return reviews, total_pages


def get_reviews_for_product(session: requests.Session, product_id: str, subcategory: str = "") -> list[dict]:
    """Collect all 1-star and 2-star reviews for a product by paginating the API."""
    reviews = []
    for star in ["1", "2"]:
        page = 1
        while True:
            data = fetch_page(session, product_id, page, star)
            if not data:
                break

            ret = data.get("ret", [])
            if not any("SUCCESS" in r for r in ret):
                if any("TOKEN_EXOIRED" in r or "TOKEN_ILLEGAL" in r for r in ret):
                    raise TokenExpiredError(ret)
                print(f"{colorize('[WARNING]')} API error star={star}: {ret}")
                break

            page_reviews, total_pages = parse_reviews(data, product_id, subcategory)
            reviews.extend(page_reviews)
            print(f"{colorize('[INFO]')} star={star} page={page}/{total_pages} → {len(page_reviews)} reviews")

            if page >= total_pages or not page_reviews:
                break
            page += 1
            time.sleep(random.uniform(0.3, 0.8))

    return reviews


def save_reviews(reviews: list[dict]) -> None:
    """Append new reviews to the Excel file, deduplicating by product_id + review_text."""
    ALIEXPRESS_REVIEWS_PATH.parent.mkdir(parents=True, exist_ok=True)
    new_df = pd.DataFrame(reviews)
    new_df["hazard_label"] = ""

    if ALIEXPRESS_REVIEWS_PATH.exists():
        existing = pd.read_excel(ALIEXPRESS_REVIEWS_PATH)
    else:
        existing = pd.DataFrame()
        print(f"{colorize('[INFO]')} Creating new {ALIEXPRESS_REVIEWS_PATH.name}")

    df = pd.concat([existing, new_df], ignore_index=True)
    df["product_id"] = df["product_id"].astype(str)
    df = df.drop_duplicates(subset=["product_id", "review_text"], keep="first")
    df = df.sort_values(by="product_id", key=lambda col: col.astype(int)).reset_index(drop=True)
    df = df[["product_id", "subcategory", "review_text", "hazard_label"]]
    df.to_excel(ALIEXPRESS_REVIEWS_PATH, index=False)
    print(f"{colorize('[DONE]')} Saved {len(df)} total reviews to {ALIEXPRESS_REVIEWS_PATH.name}")


def main() -> None:
    """Load cookies, iterate over product IDs, collect reviews, and save to Excel."""
    print(CDP_INSTRUCTION)
    input()

    start = time.time()
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0] if browser.contexts else browser.new_context()

        page = context.new_page()
        page.goto(ALIEXPRESS_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(random.randint(2000, 5000))

        session = requests.Session()
        refresh_cookies_cdp(session, page)

        all_reviews = []

        ids_file = find_ids_file(ALIEXPRESS_DATA_PATH, f"aliexpress_us_{ALIEXPRESS_IDS_CATEGORY}_ids.json")
        raw = json.loads(ids_file.read_text())
        products = [
            (entry["id"], entry.get("subcategory", "")) if isinstance(entry, dict) else (entry, "")
            for entry in raw
        ]
        print(f"\n{colorize('[INFO]')} Collecting reviews for {len(products)} products via API")

        session_start = time.time()
        for i, (pid, subcategory) in enumerate(products, start=1):
            print(f"\n{colorize('[INFO]')} {i}/{len(products)} ===== Product {pid} =====")

            while True:
                try:
                    reviews = get_reviews_for_product(session, str(pid), subcategory)
                    break
                except TokenExpiredError:
                    elapsed = int(time.time() - session_start)
                    if all_reviews:
                        save_reviews(all_reviews)
                    print(f"{colorize('[WARNING]')} Token expired after {elapsed // 60}m {elapsed % 60}s. Updating cookies...")
                    refresh_cookies_cdp(session, page)
                    time.sleep(60)
                    session_start = time.time()

            all_reviews.extend(reviews)
            print(f"{colorize('[OK]')} {len(reviews)} reviews collected for {pid}")

            if all_reviews and i % 500 == 0:
                save_reviews(all_reviews)

        if all_reviews:
            save_reviews(all_reviews)
        else:
            print(f"{colorize('[WARNING]')} No reviews collected.")

        play_alert_sound("Glass")
        elapsed = int(time.time() - start)
        print(f"{colorize('[INFO]')} Time: {elapsed // 60}m {elapsed % 60}s")


if __name__ == "__main__":
    main()