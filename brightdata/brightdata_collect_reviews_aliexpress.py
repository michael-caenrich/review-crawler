"""
Collect 1-star and 2-star reviews from AliExpress using Bright Data Browser API.

Before running:
    pip install playwright pandas openpyxl python-dotenv
    playwright install chromium

    Create a .env file in the project root with:
        BRIGHTDATA_AUTH=<username>:<password>

Output: Excel file with review_text, product_id, is_negative, hazard_label columns.
"""
import asyncio
import os

import pandas as pd
from playwright.async_api import Playwright, async_playwright

from config import (
    ALIEXPRESS_DATA_PATH,
    ALIEXPRESS_PRODUCT_IDS,
    ALIEXPRESS_SELECTORS,
    NEGATIVE_KEYWORDS_EN,
)

from dotenv import load_dotenv
load_dotenv()

AUTH = os.getenv("BRIGHTDATA_AUTH")
if not AUTH:
    raise ValueError("BRIGHTDATA_AUTH environment variable is not set")

BASE_URL = "https://www.aliexpress.com/item/{product_id}.html"

MAX_SCROLL_ROUNDS = 20


async def close_popups(page) -> None:
    for selector in ['button[aria-label="close"]', 'button[class*="close"]', '.next-dialog-close']:
        try:
            btn = await page.query_selector(selector)
            if btn:
                await btn.click()
                await page.wait_for_timeout(500)
        except Exception:
            continue


async def click_star_filter(page, filter_key: str) -> bool:
    """Open the ratings dropdown then click the matching star filter. Returns True if clicked."""
    try:
        dropdown = await page.query_selector(ALIEXPRESS_SELECTORS['ratings_dropdown'])
        if not dropdown:
            print(f'  Warning: ratings dropdown not found')
            return False
        await dropdown.click()
        await page.wait_for_timeout(800)

        btn = page.locator(ALIEXPRESS_SELECTORS[filter_key]).first
        if await btn.count() == 0:
            print(f'  Warning: {filter_key} option not found in dropdown')
            return False
        await btn.click()
        await page.wait_for_timeout(1500)
        return True
    except Exception as e:
        print(f'  Warning: could not click {filter_key} filter: {e}')
    return False


async def click_view_more_button(page) -> None:
    """Click "View more" once to open the reviews popup."""
    try:
        btn = await page.query_selector(ALIEXPRESS_SELECTORS['view_more'])
        if btn:
            await btn.scroll_into_view_if_needed()
            await btn.click()
            await page.wait_for_timeout(1500)
        else:
            print('  Warning: "View more" button not found')
    except Exception as e:
        print(f'  Warning: could not click "View more": {e}')


async def scroll_to_load_all(page) -> None:
    """Scroll down until no new reviews load for 2 consecutive rounds."""
    prev_count = 0
    unchanged_rounds = 0
    for _ in range(MAX_SCROLL_ROUNDS):
        try:
            elements = await page.query_selector_all(ALIEXPRESS_SELECTORS['review_text'])
            current_count = len(elements)
            if current_count == 0:
                return
            if current_count == prev_count:
                unchanged_rounds += 1
                if unchanged_rounds >= 2:
                    break
            else:
                unchanged_rounds = 0
            prev_count = current_count
            await elements[-1].scroll_into_view_if_needed()
            await page.wait_for_timeout(1500)
        except Exception as e:
            print(f'  Warning: scroll error: {e}')
            break


async def extract_reviews(page, product_id: int) -> list[dict]:
    reviews = []
    try:
        elements = await page.query_selector_all(ALIEXPRESS_SELECTORS['review_text'])
        for el in elements:
            text = (await el.inner_text()).strip()
            if text:
                reviews.append({'product_id': product_id, 'review_text': text})
    except Exception as e:
        print(f'  Warning: extraction error: {e}')
    return reviews


async def scroll_to_reviews(page) -> None:
    """Scroll down until the 'View more' button is visible."""
    for _ in range(10):
        try:
            btn = await page.query_selector(ALIEXPRESS_SELECTORS['view_more'])
            if btn:
                await btn.scroll_into_view_if_needed()
                await page.wait_for_timeout(1000)
                return
            await page.evaluate('window.scrollBy(0, window.innerHeight)')
            await page.wait_for_timeout(800)
        except Exception as e:
            print(f'  Warning: scroll failed: {e}')


async def get_reviews(playwright: Playwright, product_id: int) -> list[dict]:
    all_reviews = []
    endpoint = f"wss://{AUTH}@brd.superproxy.io:9222"

    browser = await playwright.chromium.connect_over_cdp(endpoint)
    context = None

    try:
        context = await browser.new_context()
        page = await context.new_page()
        url = BASE_URL.format(product_id=product_id)

        print(f'  Navigating to: {url}')
        await page.goto(url, timeout=120_000, wait_until='domcontentloaded')
        await page.wait_for_timeout(3_000)
        await close_popups(page)
        await scroll_to_reviews(page)
        await click_view_more_button(page)

        seen: set[tuple] = set()
        for filter_key in ['1_star', '2_star']:
            pre_count = len(await page.query_selector_all(ALIEXPRESS_SELECTORS['review_text']))
            clicked = await click_star_filter(page, filter_key)
            if not clicked:
                continue

            for _ in range(10):
                await page.wait_for_timeout(500)
                count = len(await page.query_selector_all(ALIEXPRESS_SELECTORS['review_text']))
                if count != pre_count:
                    break

            if await page.locator(ALIEXPRESS_SELECTORS["review_text"]).count() == 0:
                continue

            await scroll_to_load_all(page)
            reviews = await extract_reviews(page, product_id)
            reviews = [r for r in reviews if (r['product_id'], r['review_text']) not in seen]
            seen.update((r['product_id'], r['review_text']) for r in reviews)
            all_reviews.extend(reviews)
            print(f'  {filter_key}: {len(reviews)} reviews')

    except Exception as e:
        print(f'  Error: {e}')
    finally:
        if context:
            await context.close()
        await browser.close()
    return all_reviews


def save_reviews(reviews: list[dict]) -> None:
    ALIEXPRESS_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

    new_df = pd.DataFrame(reviews)
    new_df['is_negative'] = new_df['review_text'].apply(
        lambda text: 1 if any(kw.lower() in text.lower() for kw in NEGATIVE_KEYWORDS_EN) else 0
    )
    new_df['hazard_label'] = ''

    if ALIEXPRESS_DATA_PATH.exists():
        existing = pd.read_excel(ALIEXPRESS_DATA_PATH)
    else:
        existing = pd.DataFrame()

    df = pd.concat([existing, new_df], ignore_index=True)
    df['product_id'] = df['product_id'].astype(str)
    df = df.drop_duplicates(subset=['product_id', 'review_text'], keep='first')
    df = df.sort_values(by='product_id').reset_index(drop=True)
    df.to_excel(ALIEXPRESS_DATA_PATH, index=False)
    print(f'Saved {len(df)} reviews to {ALIEXPRESS_DATA_PATH.name}')


async def main():
    all_reviews = []

    async with async_playwright() as pw:
        for product_id in ALIEXPRESS_PRODUCT_IDS:
            print(f'\n===== Product {product_id} =====')
            reviews = await get_reviews(pw, product_id)
            all_reviews.extend(reviews)
            print(f'Total: {len(reviews)} reviews')

    if all_reviews:
        save_reviews(all_reviews)
    else:
        print('No reviews collected.')


if __name__ == '__main__':
    asyncio.run(main())