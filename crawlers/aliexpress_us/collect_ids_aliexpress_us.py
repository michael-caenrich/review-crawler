"""
Collect product IDs from an AliExpress category page (US site).

Flow:
    1. Opens aliexpress.com and lists available categories.
    2. You pick a category number in the terminal.
    3. Scrolls that category page to load all products.
    4. Extracts product IDs and saves them.

Before running:
    1. Quit Chrome completely.
    2. Reopen Chrome with a dedicated debug profile:
       /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
           --remote-debugging-port=9222 \
           --user-data-dir=$HOME/chrome-aliexpress-profile
    3. Log into AliExpress in that Chrome window.
    4. Run this script.

Output:
    - data/aliexpress_us/aliexpress_us_{category}_{count}_ids.json
"""
import json
import pathlib
import random
import re
import time

from playwright.sync_api import Page, sync_playwright

from cli_utils import colorize
from config import CDP_URL, ALIEXPRESS_CATEGORY_IDS_DIR, ALIEXPRESS_SELECTORS

ALIEXPRESS_HOME = "https://www.aliexpress.com"
PRODUCT_ID_RE = re.compile(r"/item/(\d+)\.html")
DEFAULT_MAX_IDS = 1000


def find_existing_file(category_slug: str) -> pathlib.Path | None:
    """Return the existing IDs file for this category, or None if not found."""
    return next(ALIEXPRESS_CATEGORY_IDS_DIR.glob(f"aliexpress_us_{category_slug}_*_ids.json"), None)


def fetch_categories(page: Page) -> list[dict]:
    """Return unique category entries {name, url} from the homepage."""
    categories: list[dict] = []
    seen: set[str] = set()

    for el in page.locator(ALIEXPRESS_SELECTORS["category"]).all():
        try:
            href = el.get_attribute("href") or ""
            name = el.inner_text().strip()
            if not href or not name or href in seen:
                continue
            seen.add(href)
            categories.append({"name": name, "url": href})
        except Exception:
            pass

    return categories


def pick_category(categories: list[dict]) -> dict:
    """Print a numbered category list and return the user's choice."""
    print(f"\n{colorize('[INFO]')} Found {len(categories)} categories:")
    for i, cat in enumerate(categories, start=1):
        print(f"  {i}. {cat['name']}")

    while True:
        raw = input(f"\n{colorize('[INFO]')} Enter category number: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(categories):
            return categories[int(raw) - 1]
        print(f"{colorize('[WARNING]')} Enter a number between 1 and {len(categories)}.")


def ask_max_ids(existing_count: int = 0) -> int:
    """Prompt the user for how many product IDs to collect."""
    if existing_count:
        prompt = f"\n{colorize('[INFO]')} File already has {existing_count} IDs. How many more to add? "
    else:
        prompt = f"\n{colorize('[INFO]')} How many product IDs to collect? (default {DEFAULT_MAX_IDS}): "

    while True:
        raw = input(prompt).strip()
        if not raw and not existing_count:
            return DEFAULT_MAX_IDS
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
        print(f"{colorize('[WARNING]')} Enter a positive number.")


def scroll_to_load_all(page: Page, max_ids: int) -> None:
    """Scroll the category page until no new product links appear or max_ids is reached."""
    print(f"{colorize('[INFO]')} Scrolling to load all products (target: {max_ids})...")
    product_link_selector = ALIEXPRESS_SELECTORS["product_link"]
    prev_count = 0
    i = 0
    pause_after = random.randint(3, 7)

    while True:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(random.randint(3000, 5000))

        count = page.locator(product_link_selector).count()
        if count == prev_count:
            page.wait_for_timeout(5000)
            count = page.locator(product_link_selector).count()
            if count == prev_count:
                print(f"{colorize('[INFO]')} Found all available IDs for this category.")
                break
        prev_count = count
        print(f"{colorize('[INFO]')} {count} product IDs found so far...")

        if count >= max_ids:
            print(f"{colorize('[OK]')} Reached target of {max_ids} IDs.")
            break

        i += 1
        if i % pause_after == 0:
            page.wait_for_timeout(random.randint(5000, 8000))
            pause_after = random.randint(3, 7)


def extract_ids(page: Page) -> list[int]:
    """Extract unique product IDs from all product links on the page."""
    ids: set[int] = set()

    for el in page.locator(ALIEXPRESS_SELECTORS["product_link"]).all():
        try:
            href = el.get_attribute("href") or ""
            match = PRODUCT_ID_RE.search(href)
            if match:
                ids.add(int(match.group(1)))
        except Exception as e:
            print(f"{colorize('[WARNING]')} Failed to read link: {e}")

    return sorted(ids)


def save_ids(ids: list[int], category_slug: str) -> None:
    """Write IDs to JSON file named with platform, category, and count."""
    path = ALIEXPRESS_CATEGORY_IDS_DIR / f"aliexpress_us_{category_slug}_{len(ids)}_ids.json"
    ALIEXPRESS_CATEGORY_IDS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ids, indent=2))
    print(f"{colorize('[DONE]')} Saved {len(ids)} IDs to {path.name}")


def main() -> None:
    """Open homepage, let user pick a category, then collect and save product IDs."""
    start = time.time()

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()

        print(f"{colorize('[INFO]')} Opening AliExpress homepage...")
        page.goto(ALIEXPRESS_HOME, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(10000)

        categories = fetch_categories(page)

        if not categories:
            print(f"{colorize('[WARNING]')} No category links found on the homepage.")
            print(f"{colorize('[INFO]')} AliExpress may have changed its layout. Check the page manually.")
            page.close()
            return

        chosen = pick_category(categories)
        slug = re.sub(r"[^a-z0-9]+", "_", chosen["name"].lower()).strip("_")

        existing_file = find_existing_file(slug)
        existing_ids: list[int] = []
        if existing_file:
            existing_ids = json.loads(existing_file.read_text())
            print(f"{colorize('[INFO]')} Found existing file: {existing_file.name} ({len(existing_ids)} IDs)")

        max_new = ask_max_ids(existing_count=len(existing_ids))

        print(f"\n{colorize('[INFO]')} Navigating to: {chosen['name']} → {chosen['url']}")
        page.goto(chosen["url"], wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(10000)

        scroll_to_load_all(page, len(existing_ids) + max_new)
        new_ids = extract_ids(page)
        page.close()

    all_ids = sorted(set(existing_ids + new_ids))
    added = len(all_ids) - len(existing_ids)
    print(f"{colorize('[INFO]')} New unique IDs added: {added} (duplicates removed: {len(new_ids) - added})")
    if added < max_new:
        print(f"{colorize('[INFO]')} This category has no more IDs — {len(all_ids)} total collected.")

    if all_ids:
        save_ids(all_ids, slug)
    else:
        print(f"{colorize('[WARNING]')} No product IDs found on the category page.")

    elapsed = int(time.time() - start)
    print(f"{colorize('[INFO]')} Time: {elapsed // 60}m {elapsed % 60}s")


if __name__ == "__main__":
    main()
