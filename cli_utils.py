"""CLI color helpers."""

import pathlib
import subprocess
import sys
from colorama import Fore, Style, init
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


def play_alert_sound() -> None:
    """Play an alert sound when captcha detected or token expired."""
    if sys.platform == "win32":
        import winsound
        winsound.MessageBeep()
    else:
        subprocess.run(["afplay", "/System/Library/Sounds/Ping.aiff"])


def find_ids_file(directory: pathlib.Path, pattern: str) -> pathlib.Path:
    """Return the IDs file matching pattern in directory, or raise FileNotFoundError."""
    match = next(directory.glob(pattern), None)
    if match is None:
        raise FileNotFoundError(
            f"No IDs file matching '{pattern}' in {directory}. Run the collect_ids script first."
        )
    return match
