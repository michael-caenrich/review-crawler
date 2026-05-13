"""
Collect 1-star and 2-star reviews from AliExpress using Chrome debug profile.

Before running:
    1. Quit Chrome completely.
    2. Reopen Chrome with a dedicated debug profile:
       /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
           --remote-debugging-port=9222 \
           --user-data-dir=$HOME/chrome-aliexpress-profile
    3. Log into AliExpress in that Chrome window.
    4. Run this script.

Output: Excel file with review_text, product_id, is_negative, and empty label columns.
"""
import random
import time

import pandas as pd
from playwright.sync_api import Page, Locator, sync_playwright

from cli_utils import colorize
from config import (
    CDP_URL,
    ALIEXPRESS_DATA_PATH,
    ALIEXPRESS_SELECTORS,
    ALIEXPRESS_PRODUCT_IDS,
    NEGATIVE_KEYWORDS_EN,
)

REVIEW_TEXT_SELECTOR = ALIEXPRESS_SELECTORS["review_text"]
SCROLL_ROUNDS = 15


def human_click(page: Page, btn: Locator) -> None:
    """Simulate a human-like click with random mouse movement."""
    btn.wait_for(state="visible", timeout=5000)
    btn.scroll_into_view_if_needed(timeout=5000)
    box = btn.bounding_box()

    if box:
        x = box["x"] + random.uniform(0.2, 0.8) * box["width"]
        y = box["y"] + random.uniform(0.2, 0.8) * box["height"]
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.5, 1.5))
        page.mouse.down()
        time.sleep(random.uniform(0.05, 0.15))
        page.mouse.up()
        time.sleep(random.uniform(0.3, 0.8))
    else:
        btn.click()


def scroll_to_popup(page: Page) -> None:
    """Scroll down to the reviews section."""
    print(f"{colorize('[INFO]')} Scrolling to 'View more' review button...")
    for _ in range(10):
        try:
            selector = ALIEXPRESS_SELECTORS["view_more"]
            btn = page.locator(selector).first
            if btn.count() > 0:
                btn.scroll_into_view_if_needed(timeout=5000)
                page.wait_for_timeout(2000)
                print(f"{colorize('[INFO]')} 'View more' button is in view.")
                return

            page.evaluate("window.scrollBy(0, window.innerHeight)")
            page.wait_for_timeout(1000)
        except Exception as e:
            print(f"{colorize('[WARNING]')} Scroll failed: {e}")


def click_view_more_button(page: Page) -> bool | None:
    """Click 'View more' to open the reviews popup. Returns True if successful."""
    selector = ALIEXPRESS_SELECTORS["view_more"]
    btn = page.locator(selector).first
    if btn.count() == 0:
        print(f"{colorize('[WARNING]')} Selector for key 'view_more' not found: {selector}")
        return None

    try:
        human_click(page, btn)
        page.wait_for_timeout(timeout=3000)
        print(f"{colorize('[OK]')} Clicked 'View more' — reviews section is open.")
        return True
    except Exception as e:
        print(f"{colorize('[WARNING]')} Failed to open reviews section: {e}")
        return False


def click_star_filter(page: Page, filter_key: str) -> None:
    """Open ratings dropdown then click the star filter by key."""
    if filter_key not in ALIEXPRESS_SELECTORS:
        raise KeyError(f"Missing selector key '{filter_key}' in ALIEXPRESS_SELECTORS in config.py")

    dropdown_selector = ALIEXPRESS_SELECTORS["ratings_dropdown"]
    dropdown = page.locator(dropdown_selector).first
    if dropdown.count() == 0:
        print(f"{colorize('[WARNING]')} Selector for key 'ratings_dropdown' not found: {dropdown_selector}")
        return

    try:
        human_click(page, dropdown)
        page.wait_for_timeout(1000)
        print(f"{colorize('[OK]')} Clicked 'All ratings' — dropdown opened.")

        star_selector = ALIEXPRESS_SELECTORS[filter_key]
        btn = page.locator(star_selector).first
        btn.wait_for(state="visible", timeout=3000)
        human_click(page, btn)
        page.wait_for_timeout(2000)
        print(f"{colorize('[OK]')} Clicked '{filter_key}' — filter applied.")
    except Exception as e:
        print(f"{colorize('[WARNING]')} Failed: {e}")


def scroll_popup_to_load_more(page: Page) -> None:
    """Scroll to the last review card repeatedly to trigger lazy loading."""
    print(f"{colorize('[INFO]')} Scrolling to load all reviews...")
    prev_count = 0

    for _ in range(SCROLL_ROUNDS):
        try:
            cards = page.locator(REVIEW_TEXT_SELECTOR)
            count = cards.count()
            if count == 0:
                print(f"{colorize('[WARNING]')} No review elements found to scroll to.")
                return
            if count == prev_count:
                break
            prev_count = count
            cards.nth(count - 1).scroll_into_view_if_needed(timeout=3000)
        except Exception as e:
            print(f"{colorize('[WARNING]')} Scroll failed: {e}")

        page.wait_for_timeout(random.randint(1500, 3000))

    total = page.locator(REVIEW_TEXT_SELECTOR).count()
    print(f"{colorize('[INFO]')} Found {total} reviews")


def extract_reviews(page: Page, product_id: int) -> list[dict]:
    """Extract visible review text from the page."""
    reviews = []

    for element in page.locator(ALIEXPRESS_SELECTORS["review_text"]).all():
        try:
            text = element.inner_text().strip()
            if text:
                reviews.append({
                    "product_id": product_id,
                    "review_text": text,
                })
        except Exception as e:
            print(f"{colorize('[WARNING]')} Failed to read review: {e}")

    return reviews


def get_reviews(product_id: int) -> list[dict]:
    """Connect to Chrome over CDP and collect reviews for one product."""
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0] if browser.contexts else browser.new_context()

        page = context.new_page()
        url = f"https://www.aliexpress.com/item/{product_id}.html"
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(random.randint(3000, 6000))
        print(f"\n{colorize('[INFO]')} Opened product {product_id} — trying to click 'View more'...")

        scroll_to_popup(page)

        view_more_popup_opened = click_view_more_button(page)

        if not view_more_popup_opened:
            print(f"{colorize('[WARNING]')} Auto-click failed. Please click 'View more' manually.")
            input(f"{colorize('[INFO]')} Press Enter when the reviews section is open... ")

        reviews = []
        for star in ["1_star", "2_star"]:
            pre_count = page.locator(ALIEXPRESS_SELECTORS["review_text"]).count()
            click_star_filter(page, star)

            for _ in range(10):
                page.wait_for_timeout(500)
                if page.locator(ALIEXPRESS_SELECTORS["review_text"]).count() != pre_count:
                    break

            if page.locator(ALIEXPRESS_SELECTORS["review_text"]).count() == 0:
                print(f"{colorize('[INFO]')} No reviews found for '{star}' filter")
                continue

            scroll_popup_to_load_more(page)
            reviews.extend(extract_reviews(page, product_id))

        page.close()

    return reviews


def save_reviews(reviews: list[dict]) -> None:
    """Save collected reviews to Excel for manual labeling."""
    ALIEXPRESS_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

    new_reviews = pd.DataFrame(reviews)
    new_reviews["is_negative"] = new_reviews["review_text"].apply(
        lambda text: 1 if any(kw.lower() in text.lower() for kw in NEGATIVE_KEYWORDS_EN) else 0
    )
    new_reviews["hazard_label"] = ""

    if ALIEXPRESS_DATA_PATH.exists():
        existing = pd.read_excel(ALIEXPRESS_DATA_PATH)
    else:
        existing = pd.DataFrame()
        print(f"{colorize('[INFO]')} A new aliexpress_reviews_raw.xlsx will be created")

    df = pd.concat([existing, new_reviews], ignore_index=True)
    df["product_id"] = df["product_id"].astype(str)
    df = df.drop_duplicates(subset=["product_id", "review_text"], keep="first")
    df = df.sort_values(by="product_id").reset_index(drop=True)
    df.to_excel(ALIEXPRESS_DATA_PATH, index=False)
    print(f"{colorize('[DONE]')} Saved {len(df)} reviews to {ALIEXPRESS_DATA_PATH.name}")


def main() -> None:
    """Collect reviews for all configured products and save them."""
    all_reviews = []

    for pid in ALIEXPRESS_PRODUCT_IDS:
        print(f"\n{colorize('[INFO]')} ===== Product {pid} =====")
        reviews = get_reviews(pid)
        all_reviews.extend(reviews)
        print(f"{colorize('[OK]')} Collected {len(reviews)} reviews for product '{pid}'")

    if all_reviews:
        save_reviews(all_reviews)
    else:
        print(f"{colorize('[WARNING]')} No reviews collected.")


if __name__ == "__main__":
    main()
