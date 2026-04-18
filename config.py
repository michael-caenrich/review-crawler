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