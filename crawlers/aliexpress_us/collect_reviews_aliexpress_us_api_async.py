"""
Collect 1-star and 2-star reviews from AliExpress via internal review API.
Async version — fetches CONCURRENCY products simultaneously for faster collection.

Before running:
    1. Quit Chrome completely.
    2. Reopen Chrome with remote debugging enabled:
       /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \
           --remote-debugging-port=9222 \
           --user-data-dir=$HOME/chrome-aliexpress-profile
    3. Log into aliexpress.us in that Chrome window.
    4. Run this script — cookies are read automatically via CDP.
"""

import asyncio
import json
import re
import sys
import time
import random
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import httpx
import pandas as pd
from playwright.async_api import async_playwright

from cli_utils import (
    colorize,
    format_elapsed,
    play_alert_sound,
    get_token,
    generate_sign,
    pick_file,
    TokenExpiredError,
)
from config import (
    ALIEXPRESS_IDS_PATH,
    ALIEXPRESS_REVIEWS_PATH,
    ALIEXPRESS_URL,
    CDP_URL,
    CDP_INSTRUCTION,
)

APP_KEY = "12574478"
API_URL = "https://acs.aliexpress.us/h5/mtop.aliexpress.review.pc.list/1.0/"
CONCURRENCY = 20
BATCH_SIZE = 3000
START_FROM_ID = ""  # set to a product ID string to resume from that point, e.g. "3256812112613248"

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
ILLEGAL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


async def _reload_and_get_cookies(page) -> dict:
    """Reload the page and return fresh aliexpress.us cookies via CDP."""
    await page.reload()
    cookies = await page.context.cookies()
    return {c["name"]: c["value"] for c in cookies if "aliexpress.us" in c["domain"]}


async def fetch_page(client: httpx.AsyncClient, product_id: str, page: int, star: str) -> dict | None:
    """Make one async API request and return the parsed JSON response, or None on failure."""
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
    sign = generate_sign(get_token(client), t, APP_KEY, data_str)

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

    for attempt in range(3):
        try:
            resp = await client.get(API_URL, params=params, headers=HEADERS, timeout=25)
            match = re.search(r"mtopjsonp\d+\((.+)\)$", resp.text)
            if not match:
                print(f"{colorize('[WARNING]')} Unexpected response: {resp.text[:200]}")
                return None
            return json.loads(match.group(1))
        except Exception as e:
            print(f"{colorize('[WARNING]')} Request failed (attempt {attempt + 1}/3): {repr(e)}")
            if attempt < 2:
                await asyncio.sleep(30)
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
        if text and not ILLEGAL_CHARS.search(text):
            reviews.append({"product_id": product_id, "subcategory": subcategory, "review_text": text})
    total_pages = int(result.get("totalPage") or result.get("maxPage") or 1)
    return reviews, total_pages


async def get_reviews_for_product(
    client: httpx.AsyncClient,
    product_id: str,
    subcategory: str,
    semaphore: asyncio.Semaphore,
    refresh_lock: asyncio.Lock,
    playwright_page,
    session_start: list[float],
    counter: list[int],
    total: int,
    all_reviews: list[dict],
    reviews_path: pathlib.Path,
) -> list[dict]:
    """Collect all 1-star and 2-star reviews for one product, with token refresh on expiry."""
    async with semaphore:
        counter[0] += 1
        reviews = []
        for star in ["1", "2"]:
            page = 1
            while True:
                try:
                    data = await fetch_page(client, product_id, page, star)
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
                    print(f"{colorize('[INFO]')} {counter[0]}/{total} {product_id} star={star} page={page}/{total_pages} → {len(page_reviews)} reviews")

                    if page >= total_pages or not page_reviews:
                        break
                    page += 1
                    await asyncio.sleep(random.uniform(0.1, 0.3))

                except TokenExpiredError:
                    async with refresh_lock:
                        elapsed = int(time.time() - session_start[0])
                        if elapsed >= 5:
                            print(f"{colorize('[WARNING]')} Token expired after {format_elapsed(elapsed)}. Updating cookies...")
                            if all_reviews:
                                save_reviews(all_reviews, reviews_path)
                            new_cookies = await _reload_and_get_cookies(playwright_page)
                            client.cookies.update(new_cookies)
                            await asyncio.sleep(60)
                            session_start[0] = time.time()
                    continue

        return reviews


def reviews_path_for(ids_file: pathlib.Path) -> pathlib.Path:
    """Derive the reviews Excel path from an IDs file stem."""
    category = ids_file.stem.removeprefix("aliexpress_us_").removesuffix("_ids")
    return ALIEXPRESS_REVIEWS_PATH.parent / f"aliexpress_us_{category}_reviews_raw.csv"


def save_reviews(reviews: list[dict], path: pathlib.Path) -> int:
    """Append new reviews to the CSV file, deduplicating by product_id + review_text."""
    path.parent.mkdir(parents=True, exist_ok=True)
    new_df = pd.DataFrame(reviews)

    if path.exists():
        existing = pd.DataFrame(pd.read_csv(path))  # type: ignore
    else:
        existing = pd.DataFrame()
        print(f"{colorize('[INFO]')} Creating new {path.name}")

    df = pd.concat([existing, new_df], ignore_index=True)
    df["product_id"] = df["product_id"].astype(str)
    df = df.drop_duplicates(subset=["product_id", "review_text"], keep="first")
    df = df.sort_values(by="product_id", key=lambda col: col.astype(int)).reset_index(drop=True)
    df = df[["product_id", "subcategory", "review_text"]]
    df.to_csv(path, index=False)
    return len(df)


async def collect_all(products: list[tuple[str, str]], playwright_page, reviews_path: pathlib.Path) -> None:
    """Fetch reviews for all products concurrently in batches, saving after each batch."""
    semaphore = asyncio.Semaphore(CONCURRENCY)
    refresh_lock = asyncio.Lock()
    session_start = [time.time()]
    counter = [0]
    total = len(products)
    all_reviews = []

    cookies_dict = await _reload_and_get_cookies(playwright_page)

    async with httpx.AsyncClient(cookies=cookies_dict) as client:
        for batch_start in range(0, len(products), BATCH_SIZE):
            batch = products[batch_start:batch_start + BATCH_SIZE]
            print(f"\n{colorize('[INFO]')} Batch {batch_start // BATCH_SIZE + 1} — products {batch_start + 1}–{batch_start + len(batch)}")

            tasks = [
                get_reviews_for_product(client, pid, subcat, semaphore, refresh_lock, playwright_page, session_start, counter, total, all_reviews, reviews_path)
                for pid, subcat in batch
            ]
            results = await asyncio.gather(*tasks)
            batch_reviews = [r for reviews in results for r in reviews]
            all_reviews.extend(batch_reviews)

            print(f"{colorize('[OK]')} {len(batch_reviews)} reviews found in batch")
            if batch_reviews:
                saved_total = save_reviews(all_reviews, reviews_path)
                print(f"{colorize('[DONE]')} {saved_total} total reviews saved")


async def main() -> None:
    """Connect to Chrome via CDP, collect reviews async, and save to CSV."""
    print(CDP_INSTRUCTION)
    input()

    start = time.time()
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()
        await page.goto(ALIEXPRESS_URL, wait_until="domcontentloaded", timeout=6000)
        await page.wait_for_timeout(random.randint(2000, 5000))

        ids_files = pick_file(ALIEXPRESS_IDS_PATH)
        single_file = len(ids_files) == 1
        for ids_file in ids_files:
            reviews_path = reviews_path_for(ids_file)
            raw = json.loads(ids_file.read_text())
            products = [
                (entry["id"], entry.get("subcategory", "")) if isinstance(entry, dict) else (entry, "")
                for entry in raw
            ]
            if START_FROM_ID and single_file:
                ids = [pid for pid, _ in products]
                start_index = ids.index(START_FROM_ID) if START_FROM_ID in ids else 0
                products = products[start_index:]
                print(f"{colorize('[INFO]')} Resuming from product {START_FROM_ID} (index {start_index})")
            print(f"\n{colorize('[INFO]')} {ids_file.stem} → {reviews_path.name}")
            print(f"{colorize('[INFO]')} Collecting reviews for {len(products)} products — {CONCURRENCY} concurrent")

            file_start = time.time()
            await collect_all(products, page, reviews_path)
            file_elapsed = int(time.time() - file_start)
            print(f"{colorize('[INFO]')} {ids_file.stem} done in {format_elapsed(file_elapsed)}")

    play_alert_sound("Glass")
    elapsed = int(time.time() - start)
    print(f"{colorize('[INFO]')} Total time: {format_elapsed(elapsed)}")


if __name__ == "__main__":
    asyncio.run(main())
