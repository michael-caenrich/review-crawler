"""
Collect product reviews from JD.com using Chrome debug profile.

Before running:
    1. Quit Chrome completely.
    2. Reopen Chrome with a dedicated debug profile:
       /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
           --remote-debugging-port=9222 \
           --user-data-dir=$HOME/chrome-jd-profile
    3. Log into JD.com in that Chrome window.
    4. Run this script.

Usage flow:
    For each product:
    - The product page opens in Chrome.
    - '全部评价' is automatically clicked to open the reviews popup.
    - If auto-click fails, you will be prompted to click manually.
    - The script auto-scrolls the popup to load more reviews, then scrapes them.

Output: Excel file with review_text, product_id, and empty label columns.
"""
import random
import time

import pandas as pd
from playwright.sync_api import Page, sync_playwright

from config import DATA_PATH, PRODUCT_IDS, JD_SELECTORS, CDP_URL
from cli_utils import colorize

# JD popup selectors — may break if JD updates their CSS class names
REVIEW_CARD_SELECTOR = ".jdc-pc-rate-card"
REVIEW_TEXT_SELECTOR = ".jdc-pc-rate-card-main-desc"

SCROLL_ROUNDS = 5         # how many times to scroll inside the popup
SCROLL_PAUSE_MS = 1500    # wait between scrolls for new reviews to load


def click_all_reviews_button(page: Page) -> bool:
    """Click '全部评价' to open the reviews popup. Returns True if successful."""
    if "全部评价" not in JD_SELECTORS:
        raise KeyError("Missing selector key '全部评价' in JD_SELECTORS in config.py")

    for selector in JD_SELECTORS["全部评价"]:
        btn = page.locator(selector).first
        print(f"{colorize('[INFO]')} Trying selector for key '全部评价': {selector}")
        if btn.count() == 0:
            print(f"{colorize('[WARNING]')} Selector for key '全部评价' not found: {selector}")
            continue

        try:
            btn.wait_for(state="visible", timeout=5000)
            btn.scroll_into_view_if_needed(timeout=5000)
            time.sleep(random.uniform(0.5, 1.5))
            btn.click()
            page.wait_for_selector(REVIEW_CARD_SELECTOR, timeout=5000)
            print(f"{colorize('[OK]')} Clicked '全部评价' — popup is open.")
            return True
        except Exception as e:
            print(f"{colorize('[WARNING]')} Failed to open '全部评价' popup: {e}")

    return False


def click_negative_filter(page: Page) -> bool | None:
    """Click '差评' to filter for negative reviews. Returns True if successful."""
    if "差评" not in JD_SELECTORS:
        raise KeyError("Missing selector key '差评' in JD_SELECTORS in config.py")

    for selector in JD_SELECTORS["差评"]:
        btn = page.locator(selector).first
        print(f"{colorize('[INFO]')} Trying selector for key '差评': {selector}")
        if btn.count() == 0:
            print(f"{colorize('[WARNING]')} Selector for key '差评' not found: {selector}")
            continue

        try:
            btn.wait_for(state="visible", timeout=5000)
            btn.scroll_into_view_if_needed(timeout=5000)
            time.sleep(random.uniform(0.5, 1.5))
            btn.click()
            # wait for stale cards to leave DOM before waiting for filtered ones to appear
            page.wait_for_selector(REVIEW_CARD_SELECTOR, state="detached", timeout=5000)
            page.wait_for_selector(REVIEW_CARD_SELECTOR, timeout=5000)
            print(f"{colorize('[OK]')} Clicked '差评' — filter applied.")
            return True
        except Exception as e:
            print(f"{colorize('[WARNING]')} Failed to click filter '差评': {e}")

    return False


def scroll_popup_to_load_more(page: Page) -> None:
    """Scroll inside the popup to trigger lazy-loaded reviews."""
    print(f"{colorize('[INFO]')} Scrolling popup to load more reviews...")

    for i in range(SCROLL_ROUNDS):
        # Scroll the last visible review card into view — this moves the
        # popup's scrollbar and triggers JD to load more.
        try:
            cards = page.locator(REVIEW_CARD_SELECTOR)
            count = cards.count()
            if count == 0:
                print(f"{colorize('[WARNING]')} No review cards found to scroll to.")
                return
            cards.nth(count - 1).scroll_into_view_if_needed(timeout=3000)
        except Exception as e:
            print(f"{colorize('[WARNING]')} Scroll failed: {e}")

        page.wait_for_timeout(SCROLL_PAUSE_MS)
        new_count = page.locator(REVIEW_CARD_SELECTOR).count()
        print(f"{colorize('[INFO]')} round {i + 1}: {new_count} reviews visible")


def extract_reviews(page: Page, product_id: int) -> list[dict[str, object]]:
    """Extract visible review text from the popup."""
    reviews = []
    text_elements = page.locator(REVIEW_TEXT_SELECTOR)
    count = text_elements.count()
    print(f"{colorize('[INFO]')} Found {count} review text elements.")

    for i in range(count):
        try:
            text = text_elements.nth(i).inner_text().strip()
            # JD wraps review text in quotes — strip them.
            text = text.strip('"').strip("\u201c").strip("\u201d").strip()
            if text:
                reviews.append({
                    "product_id": product_id,
                    "review_text": text
                })
        except Exception as e:
            print(f"{colorize('[WARNING]')} Failed to read review {i}: {e}")

    return reviews


def get_reviews(product_id: int) -> list[dict[str, object]]:
    """Connect to Chrome over CDP and collect reviews for one product."""
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0] if browser.contexts else browser.new_context()

        page = context.new_page()
        url = f"https://item.jd.com/{product_id}.html"
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        print(f"\n{colorize('[INFO]')} Opened product {product_id} — trying to click '全部评价'...")
        all_reviews_popup_opened = click_all_reviews_button(page)
        if not all_reviews_popup_opened:
            print(f"{colorize('[WARNING]')} Auto-click failed. Please click '全部评价' manually, then press Enter.")
            input(f"{colorize('[INFO]')} Press Enter when the popup is open... ")

        print(f"{colorize('[INFO]')} Trying to click '差评'...")
        result = click_negative_filter(page)
        if result is None:
            print(f"{colorize('[INFO]')} No '差评' filter  for product {product_id} not found")
        elif not result:
            print(f"{colorize('[WARNING]')} Auto-click failed. Please click '差评' manually, then press Enter.")
            input(f"{colorize('[INFO]')} Press Enter... ")

        scroll_popup_to_load_more(page)
        reviews = extract_reviews(page, product_id)

        page.close()

    return reviews


def save_reviews(reviews: list[dict[str, object]]) -> None:
    """Save collected reviews to Excel for manual labeling."""
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

    new_reviews = pd.DataFrame(reviews)

    if DATA_PATH.exists():
        existing = pd.read_excel(DATA_PATH)
    else:
        existing = pd.DataFrame()
        print(f"{colorize('[INFO]')} A new reviews_raw.xlsx will be created")

    if "is_negative" not in new_reviews.columns:
        new_reviews["is_negative"] = 1

    if "hazard_label" not in new_reviews.columns:
        new_reviews["hazard_label"] = ""

    for column in ["is_negative", "hazard_label"]:
        if column not in existing.columns:
            existing[column] = ""

    df = pd.concat([existing, new_reviews], ignore_index=True)
    df = df.drop_duplicates(subset=["product_id", "review_text"], keep="first")
    df = df.sort_values(by="product_id").reset_index(drop=True)
    df.to_excel(DATA_PATH, index=False)
    print(f"{colorize('[DONE]')} Saved {len(df)} reviews to {DATA_PATH.name}")


def main() -> None:
    """Collect reviews for all configured products and save them if any are found."""
    all_reviews = []

    for pid in PRODUCT_IDS:
        print(f"\n{colorize('[INFO]')} ===== Product {pid} =====")
        reviews = get_reviews(pid)
        print(f"{colorize('[OK]')} Collected {len(reviews)} reviews for product {pid}")
        all_reviews.extend(reviews)

    if all_reviews:
        save_reviews(all_reviews)
    else:
        print(f"{colorize('[WARNING]')} No reviews collected.")


if __name__ == "__main__":
    main()