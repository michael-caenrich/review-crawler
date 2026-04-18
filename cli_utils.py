"""CLI color helpers."""

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

