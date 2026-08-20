"""
Logging.

Two destinations:
  * the terminal (readable, colourised)
  * data/logs/outreach-YYYY-MM-DD.log (permanent record)

Secrets are scrubbed from every message before it is written, so an API key
that accidentally ends up in an exception string never reaches a log file.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any

from rich.console import Console
from rich.logging import RichHandler

from src.config import LOGS_DIR, settings

console = Console()

_SECRET_VALUES = [
    v
    for v in (
        settings.anthropic_api_key,
        settings.tavily_api_key,
        settings.serper_api_key,
        settings.bevigrow_password,
    )
    if v and len(v) >= 8
]

# Catches "sk-ant-...", bearer tokens and long random blobs even if the exact
# value is not one we know about.
_SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{20,}"),
    re.compile(r"(?i)(api[_-]?key|password|token|secret)\s*[=:]\s*\S+"),
]


def scrub(text: Any) -> str:
    """Remove anything secret from a string before it is logged or printed."""
    s = str(text)
    for value in _SECRET_VALUES:
        s = s.replace(value, "***REDACTED***")
    for pattern in _SECRET_PATTERNS:
        s = pattern.sub("***REDACTED***", s)
    return s


class _ScrubFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = scrub(record.getMessage())
            record.args = ()
        except Exception:  # never let logging itself crash a run
            pass
        return True


_configured = False


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging once; safe to call repeatedly."""
    global _configured
    logger = logging.getLogger("bevigrow")

    if _configured:
        return logger

    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.propagate = False

    scrubber = _ScrubFilter()

    console_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        show_path=False,
        show_time=True,
        markup=False,
    )
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.addFilter(scrubber)
    logger.addHandler(console_handler)

    log_file = LOGS_DIR / f"outreach-{date.today().isoformat()}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s")
    )
    file_handler.addFilter(scrubber)
    logger.addHandler(file_handler)

    # Quieten noisy third-party loggers.
    for noisy in ("urllib3", "httpx", "httpcore", "googleapiclient", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True
    logger.debug("Logging initialised -> %s", log_file)
    return logger


def get_logger(name: str = "bevigrow") -> logging.Logger:
    setup_logging()
    return logging.getLogger(name if name.startswith("bevigrow") else f"bevigrow.{name}")
