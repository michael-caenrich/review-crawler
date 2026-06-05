"""
Fetch all AliExpress US categories and their subcategory names from the API.

Run this script to get a dict[str, list[str]] you can use to populate
ALIEXPRESS_CATEGORIES_US in config.py.
"""

import json
import pathlib
import random
import sys
import time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import requests

from cli_utils import colorize, get_token, generate_sign, get_cookies, TokenExpiredError
from config import COOKIES_PATH, ALIEXPRESS_DATA_PATH

APP_KEY = "24815441"
API_URL = "https://recom-acs.aliexpress.com/h5/mtop.relationrecommend.aliexpressseorecommend.recommend/1.0/"

HEADERS = {
    "accept": "application/json",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.aliexpress.com",
    "referer": "https://www.aliexpress.com/",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
}


def fetch_tab(session: requests.Session, tab_id: str) -> dict | None:
    """Fetch category and subcategory names for a given tab from the AliExpress API."""
    t = str(int(time.time() * 1000))
    inner_params = {
        "lang": "en",
        "shpt_co": "US",
        "clientType": "pc",
        "categoryRequest": "categoryPageMain",
        "categoryTab": tab_id,
    }
    params_str = json.dumps(inner_params, separators=(",", ":"))
    data_str = json.dumps({"appId": "35917", "params": params_str}, separators=(",", ":"))
    sign = generate_sign(get_token(session), t, APP_KEY, data_str)
    url_params = {
        "jsv": "2.5.1", "appKey": APP_KEY, "t": t, "sign": sign,
        "api": "mtop.relationrecommend.AliexpressSeoRecommend.recommend",
        "v": "1.0", "timeout": "10000", "type": "originaljson", "dataType": "jsonp",
    }
    try:
        resp = session.post(API_URL, params=url_params, data={"data": data_str}, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        ret = result.get("ret", [])
        if not any("SUCCESS" in r for r in ret):
            if any("TOKEN_EXOIRED" in r or "TOKEN_ILLEGAL" in r for r in ret):
                raise TokenExpiredError(ret)
            print(f"{colorize('[WARNING]')} API error for tab '{tab_id}': {ret}")
            return None
        return result
    except TokenExpiredError:
        raise
    except Exception as e:
        print(f"{colorize('[WARNING]')} Request failed for tab '{tab_id}': {e}")
        return None


def fetch_category_tree(session: requests.Session) -> dict[str, list[str]]:
    """Return all categories and their subcategory names as dict[str, list[str]]."""

    # Step 1: fetch any tab to discover all available category tabs
    first = fetch_tab(session, "automotive")
    if not first:
        return {}

    tab_items = first.get("data", {}).get("data", {}).get("categoryTabs", {}).get("items", [])
    if not tab_items:
        print(f"{colorize('[WARNING]')} No category tabs found.")
        return {}

    print(f"{colorize('[INFO]')} Found {len(tab_items)} category tabs")

    # Step 2: for each tab fetch its subcategories
    tree: dict[str, list[str]] = {}
    for tab in tab_items:
        tab_id = tab.get("id", "")
        tab_title = tab.get("title", tab_id)
        if not tab_id:
            continue

        data = fetch_tab(session, tab_id)
        if not data:
            continue

        modules = data.get("data", {}).get("data", {}).get("modules", [])
        subcats = []
        for module in modules:
            items = module.get("data", {}).get("items", [])
            if items and "#" in items[0].get("id", ""):
                subcats = [item["title"] for item in items if item.get("title")]
                break

        if subcats:
            tree[tab_title] = subcats
            print(f"{colorize('[OK]')} {tab_title}: {len(subcats)} subcategories")

        time.sleep(random.uniform(0.5, 1.0))

    return tree


def main() -> None:
    """Load cookies, fetch category tree, and save to JSON."""
    session = requests.Session()
    session.cookies.update(json.loads(COOKIES_PATH.read_text()))

    while True:
        try:
            tree = fetch_category_tree(session)
            break
        except TokenExpiredError:
            input(f"{colorize('[WARNING]')} Token expired. Paste fresh cookies into raw_cookies.txt and press Enter...")
            get_cookies()
            session.cookies.update(json.loads(COOKIES_PATH.read_text()))
            time.sleep(60)

    tree = {k: sorted(v) for k, v in sorted(tree.items())}
    output = ALIEXPRESS_DATA_PATH / "aliexpress_us_categories.json"
    output.write_text(json.dumps(tree, indent=2, ensure_ascii=False))
    print(f"\n{colorize('[DONE]')} {len(tree)} categories saved to {output.name}")


if __name__ == "__main__":
    main()
