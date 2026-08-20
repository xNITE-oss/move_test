from __future__ import annotations

import logging
import sys


class _Formatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def __init__(self, colored: bool) -> None:
        super().__init__("%(asctime)s %(levelname)-7s %(name)-22s %(message)s", "%H:%M:%S")
        self.colored = colored

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        if self.colored:
            color = self.COLORS.get(record.levelname, "")
            return f"{color}{text}{self.RESET}"
        return text


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_Formatter(colored=sys.stdout.isatty()))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    for noisy in ("httpx", "httpcore", "urllib3", "anthropic", "openai", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
