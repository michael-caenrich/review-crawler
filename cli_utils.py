"""Shared CLI utilities: terminal colors, alerts, file helpers, and cookie setup."""


class TokenExpiredError(Exception):
    pass

import json
import hashlib
import pathlib
import subprocess
import sys

import requests
from playwright.sync_api import Page
from colorama import Fore, Style, init
from requests import Session

from config import ALIEXPRESS_DATA_PATH, COOKIES_PATH

init()


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


def find_ids_file(directory: pathlib.Path, pattern: str) -> pathlib.Path:
    """Return the IDs file matching pattern in directory, or raise FileNotFoundError."""
    match = next(directory.glob(pattern), None)
    if match is None:
        raise FileNotFoundError(
            f"No IDs file matching '{pattern}' in {directory}. Run the collect_ids script first."
        )
    return match


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
    page.reload()
    cookies = page.context.cookies()
    cookies_dict = {c["name"]: c["value"] for c in cookies if "aliexpress.us" in c["domain"]}
    session.cookies.update(cookies_dict)


def ask_max_ids(existing_count: int = 0, default: int = 1000) -> int:
    """Ask user for max number of IDs to return."""
    if existing_count:
        prompt = f"\n{colorize('[INFO]')} File already has {existing_count} IDs. How many more to add? "
    else:
        prompt = f"\n{colorize('[INFO]')} How many product IDs to collect? (default {default}): "

    while True:
        raw = input(prompt).strip()
        if not raw and not existing_count:
            return default
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
        print(f"{colorize('[WARNING]')} Enter a positive number.")