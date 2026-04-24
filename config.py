"""Store input and output file paths."""

import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "reviews_raw.xlsx"
OUTPUT_PATH = BASE_DIR / "output" / "results.xlsx"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

PRODUCT_IDS = [
    100112573693,    # children's toy
    100011166107,    # children's toy
    100190960941,    # children's toy
    100014327793,    # skincare
    100331533320,    # skincare
    10151921151284,  # skincare
    100043899267,    # charger
    100266373302,    # charger
    100251221945,    # charger
]

JD_SELECTORS = {
    "全部评价": ["#comment-root > div.all-btn > div", "text=全部评价"],
    "差评": ["#rateList span:has-text('差评')", "text=差评"],
}

CDP_URL = "http://127.0.0.1:9222"