"""
Collect product reviews from JD.com using an already opened Chrome session.

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
    - You click '全部评价' to open the reviews popup.
    - Press Enter in Terminal.
    - The script auto-scrolls the popup to load more reviews, then scrapes them.

Output: Excel file with review_text, product_id, and empty label columns.
"""

import pandas as pd
from playwright.sync_api import Page, sync_playwright

from config import DATA_PATH
from cli_utils import colorize

CDP_URL = "http://127.0.0.1:9222"

PRODUCT_IDS = [
    100112573693,  # children's toy
]

# Concrete selectors for JD's review popup (the 全部评价 modal).
REVIEW_CARD_SELECTOR = ".jdc-pc-rate-card"
REVIEW_TEXT_SELECTOR = ".jdc-pc-rate-card-main-desc"

SCROLL_ROUNDS = 5         # how many times to scroll inside the popup
SCROLL_PAUSE_MS = 1500    # wait between scrolls for new reviews to load


def click_all_reviews_button(page: Page) -> bool:
    """
    Scroll down until the '全部评价' button is visible, then click it.
    Tries multiple selectors in order. Returns True if popup opened.
    """
    selectors = [
        ".all-btn",
        "text=全部评价",
        ".comment-count",
        ".tab-con >> text=全部评价",
    ]

    for selector in selectors:
        try:
            btn = page.locator(selector).first
            if btn.count() == 0:
                continue
            print(f"{colorize('[INFO]')} Trying selector: {selector}")
            btn.scroll_into_view_if_needed(timeout=5000)
            page.wait_for_timeout(1000)
            btn.click()
            page.wait_for_selector(REVIEW_CARD_SELECTOR, timeout=8000)
            print(f"{colorize('[OK]')} Clicked '全部评价' — popup is open.")
            return True
        except Exception as exc:
            print(f"{colorize('[WARNING]')} '{selector}' failed: {exc}")
            continue

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
        except Exception as exc:
            print(f"{colorize('[WARNING]')} Scroll failed: {exc}")

        page.wait_for_timeout(SCROLL_PAUSE_MS)
        new_count = page.locator(REVIEW_CARD_SELECTOR).count()
        print(f"{colorize('[INFO]')} round {i + 1}: {new_count} reviews visible")


def extract_reviews(page: Page, product_id: int) -> list[dict]:
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
                    "review_text": text,
                })
        except Exception as exc:
            print(f"{colorize('[WARNING]')} Failed to read review {i}: {exc}")

    return reviews


def get_reviews(product_id: int) -> list[dict]:
    """Connect to Chrome over CDP and collect reviews for one product."""

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0] if browser.contexts else browser.new_context()

        page = context.new_page()
        url = f"https://item.jd.com/{product_id}.html"
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        print(f"\n{colorize('[INFO]')} Opened product {product_id} — trying to click '全部评价'...")
        success = click_all_reviews_button(page)

        if not success:
            print(f"{colorize('[WARNING]')} Auto-click failed. Please click '全部评价' manually, then press Enter.")
            input(f"{colorize('[INFO]')} Press Enter when the popup is open... ")

        scroll_popup_to_load_more(page)
        reviews = extract_reviews(page, product_id)

        page.close()

    return reviews


def save_reviews(reviews: list[dict]) -> None:
    """Save collected reviews to Excel for manual labeling."""
    df = pd.DataFrame(reviews)
    df["is_negative"] = ""
    df["hazard_label"] = ""
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
