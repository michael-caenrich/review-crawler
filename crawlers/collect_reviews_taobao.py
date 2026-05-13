"""
Collect reviews from Taobao using Chrome debug profile

Before running:
    1. Quit Chrome completely.
    2. Reopen Chrome with a dedicated debug profile:
       /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
           --remote-debugging-port=9222 \
           --user-data-dir=$HOME/chrome-taobao-profile
    3. Log into taobao.com in that Chrome window.
    4. Run this script.

Usage flow:
    For each product:
    - The product page opens in Chrome.
    - '查看全部评价' is automatically clicked to open the reviews popup.
    - If auto-click fails, you will be prompted to click manually.
    - The script auto-scrolls the popup to load more reviews, then scrapes them.

Output: Excel file with review_text, product_id, is_negative, and empty label columns.
"""

import random
import time

import pandas as pd
from playwright.sync_api import Page, sync_playwright

from cli_utils import colorize
from config import CDP_URL, TAOBAO_DATA_PATH, TAOBAO_SELECTORS, TAOBAO_PRODUCT_IDS, NEGATIVE_KEYWORDS

# Taobao popup selectors — may break if Taobao updates their CSS class names
REVIEW_CARD_SELECTOR = TAOBAO_SELECTORS["review_card"]
REVIEW_TEXT_SELECTOR = TAOBAO_SELECTORS["review_text"]

SCROLL_ROUNDS = 20         # how many times to scroll inside the popup


def click_all_reviews_button(page: Page) -> bool | None:
    """Click '查看全部评价' to open the reviews popup. Return True if successful."""
    if '查看全部评价' not in TAOBAO_SELECTORS:
        raise KeyError("Missing selector key '查看全部评价' in TAOBAO_SELECTORS in config.py")

    button_found = False
    for selector in TAOBAO_SELECTORS["查看全部评价"]:
        btn = page.locator(selector).first
        print(f"{colorize('[INFO]')} Trying selector for key '查看全部评价': {selector}")
        if btn.count() == 0:
            print(f"{colorize('[WARNING]')} Selector for key '查看全部评价' not found: '{selector}'")
            continue

        button_found = True
        try:
            btn.wait_for(state="visible", timeout=5000)
            btn.scroll_into_view_if_needed(timeout=5000)
            time.sleep(random.uniform(0.5, 1.5))
            btn.click()
            page.wait_for_selector(REVIEW_CARD_SELECTOR, timeout=5000)
            print(f"{colorize('[OK]')} Clicked '查看全部评价' — popup is open.")
            return True
        except Exception as e:
            print(f"{colorize('[WARNING]')} Failed to open '查看全部评价' popup: {e}")

    return None if not button_found else False


def scroll_popup_to_load_more(page: Page) -> None:
    """Scroll inside the popup to trigger lazy-loaded reviews."""
    print(f"{colorize('[INFO]')} Scrolling to load more reviews...")

    prev_count = 0
    for _ in range(SCROLL_ROUNDS):
        try:
            cards = page.locator(REVIEW_CARD_SELECTOR)
            count = cards.count()
            if count == 0:
                print(f"{colorize('[WARNING]')} No review cards found to scroll to.")
                return
            if count == prev_count:
                break
            prev_count = count
            cards.nth(count - 1).scroll_into_view_if_needed(timeout=3000)
        except Exception as e:
            print(f"{colorize('[WARNING]')} Scroll failed: {e}")

        page.wait_for_timeout(random.randint(1000, 2000))

    total = page.locator(REVIEW_CARD_SELECTOR).count()
    print(f"{colorize('[INFO]')} Found {total} reviews")


def extract_reviews(page: Page, product_id: int) -> list[dict[str, object]]:
    """Extract visible review text from the popup."""
    reviews = []

    text_elements = page.locator(REVIEW_TEXT_SELECTOR)
    count = text_elements.count()
    if count == 0:
        print(f"{colorize('[WARNING]')} No review text found — selector may have changed.")
        return reviews

    for i in range(count):
        try:
            text = text_elements.nth(i).get_attribute("title")
            if not text:
                text = text_elements.nth(i).inner_text()
            text = text.strip()
            if text:
                reviews.append({
                    "product_id": product_id,
                    "review_text": text,
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
        url = f"https://item.taobao.com/item.htm?id={product_id}"
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        print(f"\n{colorize('[INFO]')} Opened product {product_id} — trying to click '查看全部评价'...")
        all_reviews_popup_opened = click_all_reviews_button(page)

        if all_reviews_popup_opened is None:
            print(f"{colorize('[INFO]')} No '查看全部评价' button — scraping visible reviews directly.")
            reviews = extract_reviews(page, product_id)
            page.close()
            return reviews
        elif not all_reviews_popup_opened:
            print(f"{colorize('[WARNING]')} Auto-click failed. Please click '查看全部评价' manually.")
            input(f"{colorize('[INFO]')} Press Enter when the popup is open... ")

        scroll_popup_to_load_more(page)
        reviews = extract_reviews(page, product_id)

        page.close()

    return reviews


def save_reviews(reviews: list[dict[str, object]]) -> None:
    """Save collected reviews to Excel for manual labeling."""
    TAOBAO_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

    new_reviews = pd.DataFrame(reviews)
    new_reviews["is_negative"] = new_reviews["review_text"].apply(
        lambda text: 1 if any(kw in text for kw in NEGATIVE_KEYWORDS) else 0
    )
    new_reviews["hazard_label"] = ""

    if TAOBAO_DATA_PATH.exists():
        existing = pd.read_excel(TAOBAO_DATA_PATH)
    else:
        existing = pd.DataFrame()
        print(f"{colorize('[INFO]')} A new taobao_reviews_raw.xlsx will be created")

    df = pd.concat([existing, new_reviews], ignore_index=True)
    df["product_id"] = df["product_id"].astype(str)
    df = df.drop_duplicates(subset=["product_id", "review_text"], keep="first")
    df = df.sort_values(by="product_id").reset_index(drop=True)
    df.to_excel(TAOBAO_DATA_PATH, index=False)
    print(f"{colorize('[DONE]')} Saved {len(df)} reviews to {TAOBAO_DATA_PATH.name}")


def main() -> None:
    """Collect reviews for all configured products and save them."""
    all_reviews = []

    for pid in TAOBAO_PRODUCT_IDS:
        print(f"\n{colorize('[INFO]')} ===== Product {pid} =====")
        reviews = get_reviews(pid)
        all_reviews.extend(reviews)
        print(f"{colorize('[OK]')} Collected {len(reviews)} reviews for product {pid}")

    if all_reviews:
        save_reviews(all_reviews)
    else:
        print(f"{colorize('[WARNING]')} No reviews collected.")


if __name__ == "__main__":
    main()