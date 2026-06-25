"""
Collect AliExpress product IDs via search/browse API.

Uses aliexpress.us/fn/search-pc/index — supports real pagination (60+ pages per subcategory).
No token signing needed, just session cookies.

Before running:
    1. Log into aliexpress.us in your browser.
    2. Open DevTools → Network → Headers (Request Headers → Cookie).
    3. Copy cookie as a single string.
    4. Paste into data/aliexpress_us/raw_cookies.txt.
    5. Run this script — you will be prompted to press Enter to continue.

Flow:
    1. User picks a category.
    2. Script iterates through all subcategories automatically.
    3. Collects all available product IDs from each subcategory.
    4. Saves deduplicated results to one JSON file per category.

Note:
    AliExpress blocks by IP after ~100 requests. When blocked, the script saves
    progress and prompts to rotate VPN before resuming. Blocks are temporary (~30-40 min),
    rotating through 10 IPs is sufficient.
"""

import json
import re
import sys
import time
import random
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import requests

from cli_utils import (
    colorize,
    format_elapsed,
    play_alert_sound,
    find_ids_file,
    get_cookies,
    TokenExpiredError,
    RateLimitError,
)
from config import (
    ALIEXPRESS_IDS_PATH,
    ALIEXPRESS_CATEGORIES_US,
    COOKIES_PATH,
)

API_URL = "https://www.aliexpress.us/fn/search-pc/index"
PAGE_VERSION = "7ece9c0cc9cf2052db74f0d1b26b7033"
START_FROM_SUBCATEGORY = "Interlocking & Magnetic Blocks"  # set to "" to run all

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
    print(f"\n{colorize('[INFO]')} ===== AliExpress Categories US =====")
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
    xsrf = session.cookies.get("XSRF-TOKEN", "")
    headers = {**HEADERS, "x-xsrf-token": xsrf} if xsrf else HEADERS
    for attempt in range(3):
        try:
            resp = session.post(API_URL, json=body, headers=headers, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"{colorize('[WARNING]')} Request failed (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(5)
    return None


def extract_ids(response: dict) -> tuple[list[str], str]:
    """Extract product IDs and next streamId from the API response, raising on auth or bot errors."""
    ret = response.get("ret", [])

    if ret and any("RGV587" in r for r in ret):
        raise RateLimitError(ret)

    if response.get("x5step") or response.get("rgv587_flag"):
        raise RateLimitError(ret)

    if ret and any("USER_VALIDATE" in r or "ILLEGAL" in r or "FAIL_AUTH" in r for r in ret):
        raise TokenExpiredError(ret)

    result = response.get("data", {}).get("result", {})
    content = result.get("mods", {}).get("itemList", {}).get("content", [])
    ids = [item["productId"] for item in content if item.get("productId")]
    page_info = result.get("pageInfo", {})
    stream_id = page_info.get("streamId") or result.get("streamId") or ""
    return ids, stream_id


def collect_subcategory(session: requests.Session, subcategory_name: str, query: str, seen_ids: set, all_entries: list[dict] | None = None, category_name: str = "", existing_file=None) -> list[dict]:
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
            except RateLimitError as e:
                elapsed = int(time.time() - session_start)
                play_alert_sound("Ping")
                print(f"{colorize('[WARNING]')} {e} — IP blocked after {format_elapsed(elapsed)}.")
                if all_entries is not None:
                    save_ids(all_entries + new_entries, category_name, existing_file=existing_file)
                print(f"{colorize('[INFO]')} Rotate your IP (VPN) and press Enter...")
                input()
                session_start = time.time()
            except TokenExpiredError as e:
                elapsed = int(time.time() - session_start)
                play_alert_sound("Ping")
                print(f"{colorize('[WARNING]')} {e} — refreshing cookies after {format_elapsed(elapsed)}...")
                if all_entries is not None and all_entries:
                    save_ids(all_entries + new_entries, category_name, existing_file=existing_file)
                print(f"\n{colorize('[INFO]')} Paste fresh cookies into raw_cookies.txt and press Enter...")
                input()
                get_cookies()
                session.cookies.update(json.loads(COOKIES_PATH.read_text()))
                time.sleep(60)
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
    ALIEXPRESS_IDS_PATH.mkdir(parents=True, exist_ok=True)
    if existing_file:
        path = existing_file
    else:
        category_slug = re.sub(r"[^a-z0-9]+", "_", category_name.lower()).strip("_")
        path = ALIEXPRESS_IDS_PATH / f"aliexpress_us_{category_slug}_ids.json"
    path.write_text(json.dumps(entries, indent=2))
    print(f"{colorize('[DONE]')} Saved {len(entries)} IDs to {path.name}")
    return path


def main() -> None:
    """Collect AliExpress product IDs with manual cookie refresh."""
    start = time.time()
    print(f"{colorize('[INFO]')} Paste fresh cookies into raw_cookies.txt and press Enter...")
    input()
    get_cookies()
    session = requests.Session()
    session.cookies.update(json.loads(COOKIES_PATH.read_text()))

    print_categories()
    choice = pick_category()
    categories_to_run = list(ALIEXPRESS_CATEGORIES_US.items()) if choice is None else [(choice[0], choice[1])]

    for category_name, category_data in categories_to_run:
        print(f"\n{colorize('[INFO]')} ===== {category_name} =====")
        subcategories = category_data["subcategories"]
        category_slug = re.sub(r"[^a-z0-9]+", "_", category_name.lower()).strip("_")
        existing_entries: list[dict] = []

        try:
            existing_file = find_ids_file(ALIEXPRESS_IDS_PATH, f"aliexpress_us_{category_slug}_ids.json")
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

        subcategory_names = list(subcategories.keys())
        start_index = subcategory_names.index(START_FROM_SUBCATEGORY) if START_FROM_SUBCATEGORY and START_FROM_SUBCATEGORY in subcategory_names else 0
        if start_index:
            print(f"{colorize('[INFO]')} Resuming from subcategory: {START_FROM_SUBCATEGORY}")

        for i, (subcategory_name, query) in enumerate(subcategories.items(), start=1):
            if i <= start_index:
                continue
            print(f"\n{colorize('[INFO]')} [{i}/{len(subcategories)}] {subcategory_name}")
            new_entries = collect_subcategory(session, subcategory_name, query, seen_ids, all_entries, category_name, existing_file)
            all_entries.extend(new_entries)
            print(f"{colorize('[OK]')} {len(new_entries)} new IDs added")

            if new_entries:
                save_ids(all_entries, category_name, existing_file=existing_file)
                if not existing_file:
                    existing_file = find_ids_file(ALIEXPRESS_IDS_PATH, f"aliexpress_us_{category_slug}_ids.json")

            if i < len(subcategories):
                time.sleep(random.uniform(3, 6))

        print(f"\n{colorize('[INFO]')} {category_name} done — {len(all_entries)} total IDs")

    play_alert_sound("Glass")
    elapsed = int(time.time() - start)
    print(f"{colorize('[INFO]')} Total time: {format_elapsed(elapsed)}")


if __name__ == "__main__":
    main()
