"""
Collect AliExpress product IDs via search/browse API.

Uses aliexpress.us/fn/search-pc/index — supports real pagination (60+ pages per subcategory).
No token signing needed, just session cookies. Uses Chrome CDP to automate cookie
refreshment when bot detection or auth errors occur.

Before running:
    1. Quit Chrome completely.
    2. Reopen Chrome with a dedicated debug profile:
       /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \
           --remote-debugging-port=9222 \
           --user-data-dir=$HOME/chrome-aliexpress-profile
    3. Log into AliExpress in that Chrome window.
    4. Run this script.

Flow:
    1. User picks a category.
    2. Script iterates through all subcategories automatically.
    3. Collects all available product IDs from each subcategory.
    4. Saves deduplicated results to one JSON file per category.
"""

import json
import re
import sys
import time
import random
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import requests
from playwright.sync_api import sync_playwright

from cli_utils import (
    colorize,
    play_alert_sound,
    find_ids_file,
    refresh_cookies_cdp,
    TokenExpiredError,
)
from config import (
    ALIEXPRESS_DATA_PATH,
    ALIEXPRESS_CATEGORIES_US,
    ALIEXPRESS_URL, CDP_URL,
    CDP_INSTRUCTION,
)

API_URL = "https://www.aliexpress.us/fn/search-pc/index"
PAGE_VERSION = "7ece9c0cc9cf2052db74f0d1b26b7033"

HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "bx-v": "2.5.36",
    "content-type": "application/json;charset=UTF-8",
    "origin": "https://www.aliexpress.us",
    "referer": "https://www.aliexpress.us/",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
}


def print_categories() -> None:
    """Print numbered list of available AliExpress US categories."""
    print(f"\n{colorize('[INFO]')}===== AliExpress Categories US =====")
    for i, category in enumerate(ALIEXPRESS_CATEGORIES_US, start=1):
        print(f"{i}. {category}")


def pick_category() -> tuple[str, dict] | None:
    """Prompt user to pick a category by number, or type 'all' to collect all categories."""
    categories = ALIEXPRESS_CATEGORIES_US
    while True:
        choice = input(f"\nEnter a number (1-{len(categories)}) or 'all': ").strip().lower()
        if choice == "all":
            return None
        try:
            number = int(choice)
            if 0 < number <= len(categories):
                category_name = list(categories)[number - 1]
                return category_name, categories.get(category_name)
        except ValueError:
            print(f"{colorize('[WARNING]')} Invalid value. Enter a number 1-{len(categories)}.")


def fetch_page(session: requests.Session, query: str, page: int, stream_id: str = "") -> dict | None:
    """POST to the search API and return the parsed JSON, or None on failure."""
    body = {
        "pageVersion": PAGE_VERSION,
        "target": "root",
        "eventName": "onChange",
        "data": {
            "SearchText": query,
            "page": page,
            "streamId": stream_id,
            "isFromCategory": "y",
            "g": "y",
            "origin": "y",
        },
        "dependency": [],
    }
    try:
        xsrf = session.cookies.get("XSRF-TOKEN", "")
        headers = {**HEADERS, "x-xsrf-token": xsrf} if xsrf else HEADERS
        resp = session.post(API_URL, json=body, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"{colorize('[WARNING]')} Request failed: {e}")
        return None


def extract_ids(response: dict) -> tuple[list[str], str]:
    """Extract product IDs and next streamId from the API response, raising on auth or bot errors."""
    if response.get("x5step") or response.get("rgv587_flag"):
        raise TokenExpiredError(f"Bot detected: {response.get('ret', [])}")

    ret = response.get("ret", [])
    if ret and any("USER_VALIDATE" in r or "ILLEGAL" in r or "FAIL_AUTH" in r for r in ret):
        raise TokenExpiredError(f"Auth failed: {ret}")

    result = response.get("data", {}).get("result", {})
    content = result.get("mods", {}).get("itemList", {}).get("content", [])
    ids = [item["productId"] for item in content if item.get("productId")]
    page_info = result.get("pageInfo", {})
    stream_id = page_info.get("streamId") or result.get("streamId") or ""
    return ids, stream_id


def collect_subcategory(session: requests.Session, page, subcategory_name: str, query: str, seen_ids: set) -> list[dict]:
    """Collect all available product IDs for one subcategory, skipping already seen IDs."""
    new_entries = []
    page_num = 1
    stream_id = ""
    session_start = time.time()

    print(f"\n{colorize('[INFO]')} Subcategory: {subcategory_name}")

    while True:
        print(f"{colorize('[INFO]')} Fetching page {page_num}...")

        while True:
            try:
                response = fetch_page(session, query, page_num, stream_id)
                if not response:
                    return new_entries
                ids, stream_id = extract_ids(response)
                break
            except TokenExpiredError as e:
                elapsed = int(time.time() - session_start)
                print(f"{colorize('[WARNING]')} {e} — refreshing cookies after {elapsed // 60}m {elapsed % 60}s...")
                refresh_cookies_cdp(session, page)
                session_start = time.time()

        if not ids:
            print(f"{colorize('[INFO]')} No more results.")
            break

        for pid in ids:
            pid_str = str(pid)
            if pid_str not in seen_ids:
                new_entries.append({"id": pid_str, "subcategory": subcategory_name})
                seen_ids.add(pid_str)

        print(f"{colorize('[OK]')} {len(new_entries)} new IDs from this subcategory so far")
        page_num += 1
        time.sleep(random.uniform(1, 2))

    return new_entries


def save_ids(entries: list[dict], category_name: str, existing_file: pathlib.Path | None = None) -> pathlib.Path:
    """Save product ID entries. Overwrites existing file or creates a new one."""
    ALIEXPRESS_DATA_PATH.mkdir(parents=True, exist_ok=True)
    if existing_file:
        path = existing_file
    else:
        category_slug = re.sub(r"[^a-z0-9]+", "_", category_name.lower()).strip("_")
        path = ALIEXPRESS_DATA_PATH / f"aliexpress_us_{category_slug}_ids.json"
    path.write_text(json.dumps(entries, indent=2))
    print(f"{colorize('[DONE]')} Saved {len(entries)} IDs to {path.name}")
    return path


def main() -> None:
    """Open Chrome via CDP, let user pick a category, collect all subcategory IDs, and save to JSON."""
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

        print_categories()
        choice = pick_category()
        categories_to_run = list(ALIEXPRESS_CATEGORIES_US.items()) if choice is None else [(choice[0], choice[1])]

        for category_name, category_data in categories_to_run:
            print(f"\n{colorize('[INFO]')} ===== {category_name} =====")
            subcategories = category_data["subcategories"]
            category_slug = re.sub(r"[^a-z0-9]+", "_", category_name.lower()).strip("_")
            existing_entries: list[dict] = []

            try:
                existing_file = find_ids_file(ALIEXPRESS_DATA_PATH, f"aliexpress_us_{category_slug}_ids.json")
                existing_entries = json.loads(existing_file.read_text())
                print(f"{colorize('[INFO]')} Found existing file: {existing_file.name}")
            except FileNotFoundError:
                existing_file = None

            existing_entries = [
                e if isinstance(e, dict) else {"id": str(e), "subcategory": ""}
                for e in existing_entries
            ]

            if existing_entries:
                answer = input(f"\n{colorize('[INFO]')} File already has {len(existing_entries)} IDs. Continue adding? (y/n): ").strip().lower()
                if answer != "y":
                    print(f"{colorize('[INFO]')} Skipping {category_name}.")
                    continue

            seen_ids = {str(e["id"]) for e in existing_entries}
            all_entries = list(existing_entries)

            for i, (subcategory_name, query) in enumerate(subcategories.items(), start=1):
                print(f"\n{colorize('[INFO]')} [{i}/{len(subcategories)}] {subcategory_name}")
                new_entries = collect_subcategory(session, page, subcategory_name, query, seen_ids)
                all_entries.extend(new_entries)
                print(f"{colorize('[OK]')} {len(new_entries)} added — {len(all_entries)} total so far")

                if new_entries:
                    save_ids(all_entries, category_name, existing_file=existing_file)
                    if not existing_file:
                        existing_file = find_ids_file(ALIEXPRESS_DATA_PATH, f"aliexpress_us_{category_slug}_ids.json")

                if i < len(subcategories):
                    time.sleep(random.uniform(3, 6))

            print(f"\n{colorize('[INFO]')} {category_name} done — {len(all_entries)} total IDs")

    play_alert_sound("Glass")
    elapsed = int(time.time() - start)
    print(f"{colorize('[INFO]')} Time: {elapsed // 60}m {elapsed % 60}s")


if __name__ == "__main__":
    main()
