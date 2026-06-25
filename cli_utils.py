"""Shared CLI utilities: terminal output, file helpers, LLM classification, cookie handling, and API signing."""

import json
import hashlib
import pathlib
import subprocess
import sys
import time

import pandas as pd
import requests
from openai import OpenAI
from playwright.sync_api import Page
from colorama import Fore, Style, init
from requests import Session

from config import ALIEXPRESS_DATA_PATH, COOKIES_PATH

init()


# --- Exceptions ---
class TokenExpiredError(Exception):
    pass


class RateLimitError(Exception):
    pass


# --- Terminal output ---
def format_elapsed(seconds: int) -> str:
    """Format elapsed seconds as human-readable string (e.g. 2h 5m 3s)."""
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {s}s"
    return f"{m}m {s}s"


def colorize(text: str) -> str:
    """Return text colorized based on status tag."""
    colors = {
        "[ERROR]": Fore.RED,
        "[WARNING]": Fore.YELLOW,
        "[DONE]": Fore.GREEN,
        "[RUN]": Fore.GREEN,
        "[OK]": Fore.GREEN,
        "[INFO]": Fore.BLUE,
    }

    color = colors.get(text, Fore.RESET)
    return f"{color}{text}{Style.RESET_ALL}"


def play_alert_sound(sound: str) -> None:
    """Play an alert sound when captcha detected or token expired."""
    if sys.platform == "win32":
        import winsound
        winsound.MessageBeep()
    else:
        subprocess.run(["afplay", f"/System/Library/Sounds/{sound}.aiff"])


# --- File helpers ---
def find_ids_file(directory: pathlib.Path, pattern: str) -> pathlib.Path:
    """Return the IDs file matching pattern in directory, or raise FileNotFoundError."""
    match = next(directory.glob(pattern), None)
    if match is None:
        raise FileNotFoundError(
            f"No IDs file matching '{pattern}' in {directory}. Run the collect_ids script first."
        )
    return match


def pick_file(directory: pathlib.Path, pattern: str = "*_ids.json") -> list[pathlib.Path]:
    """List available files matching pattern in directory and let user pick one or all."""
    files = sorted(directory.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No files matching '{pattern}' found in {directory}")
    print(f"\n{colorize('[INFO]')} ===== Available Files =====")
    for i, f in enumerate(files, start=1):
        print(f"{i}. {f.stem}")
    while True:
        choice = input(f"\nEnter a number, e.g. '1', multiple '1 3 5', or 'all': ").strip().lower()
        if choice == "all":
            return files
        try:
            indices = [int(x) for x in choice.split()]
            if all(0 < n <= len(files) for n in indices):
                return [files[n - 1] for n in indices]
        except ValueError:
            pass
        print(f"{colorize('[WARNING]')} Invalid value. Enter numbers 1-{len(files)}, multiple numbers, or 'all'.")


# --- LLM classification ---
def classify_batch(reviews: list[dict[str, str | int]], prompt: str, model: str, api_key: str | None, base_url: str | None = None) -> list[int]:
    """Classify a batch of reviews and return 0/1 labels."""
    lines = []
    for index, review in enumerate(reviews, start=1):
        text = str(review["review_text"])[:300]
        lines.append(f"{index}. {text}")

    numbered = "\n".join(lines)

    client = OpenAI(api_key=api_key, base_url=base_url)
    messages: list = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": numbered},
    ]

    for attempt in range(3):
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.1,
                max_tokens=500,  # max_completion_tokens for OpenAI API
            )
            response = completion.choices[0].message.content
            if response is None:
                return []
            response = response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(response)
        except Exception as e:
            print(f"{colorize('[WARNING]')} Request failed (attempt {attempt + 1}/3): {repr(e)}")
            if attempt < 2:
                time.sleep(10)

    return []


def save_progress(reviews: list[dict[str, str | int]], labels: list[int], output_path: pathlib.Path, col: str) -> None:
    """Append labeled batch to checkpoint CSV."""
    if not labels:
        return

    for review, label in zip(reviews, labels):
        review[col] = label

    header = not output_path.exists()
    df = pd.DataFrame(reviews)
    df.to_csv(output_path, index=False, mode="a", header=header)


# --- Cookie handling ---
def get_cookies(raw: str = "") -> None:
    """Parse raw cookie string and save to JSON. Reads raw_cookies.txt if no string provided."""
    if not raw:
        raw_cookies = ALIEXPRESS_DATA_PATH / "raw_cookies.txt"
        if not raw_cookies.exists():
            print(f"{colorize('[WARNING]')} File raw_cookies.txt doesn't exist.")
            return
        raw = raw_cookies.read_text().strip()
        if not raw:
            print(f"{colorize('[WARNING]')} File raw_cookies.txt is empty.")
            return

    cookies = {}
    for item in raw.split(";"):
        item = item.strip()
        if "=" in item:
            key, value = item.split("=", 1)
            cookies[key.strip()] = value.strip()

    if not cookies:
        print(f"{colorize('[WARNING]')} No cookies parsed.")
        return

    COOKIES_PATH.write_text(json.dumps(cookies, indent=2))
    print(f"{colorize('[DONE]')} {len(cookies)} cookies saved to {COOKIES_PATH.name}")


# --- API signing ---
def get_token(session: requests.Session | object) -> str:
    """Extract the token from the _m_h5_tk session cookie (part before the underscore)."""
    try:
        cookie = session.cookies.get("_m_h5_tk") or ""
    except Exception:
        # httpx raises CookieConflict when multiple domains have the same cookie name
        # fall back to iterating the underlying jar directly
        try:
            cookie = next((c.value for c in session.cookies.jar if c.name == "_m_h5_tk"), "") or ""
        except Exception:
            cookie = next((c.value for c in session.cookies if c.name == "_m_h5_tk"), "") or ""
    return cookie.split("_")[0] if "_" in cookie else cookie


def generate_sign(token: str, t: str, app_key: str, data_str: str) -> str:
    """Generate the request signature using AliExpress mtop formula: md5(token&t&appKey&data)."""
    raw = f"{token}&{t}&{app_key}&{data_str}"
    return hashlib.md5(raw.encode()).hexdigest()


def refresh_cookies_cdp(session: Session, page: Page) -> None:
    """Reload the aliexpress.us page via CDP and update session cookies."""
    # page.reload()
    cookies = page.context.cookies()
    cookies_dict = {c["name"]: c["value"] for c in cookies if "aliexpress.us" in c["domain"]}
    session.cookies.update(cookies_dict)
