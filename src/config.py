"""
Central configuration for the BeviGrow outreach system.

Everything secret is read from the .env file at the project root.
Nothing secret is ever written into source code or into a log file.

Import this once:

    from src.config import settings
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent

CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
RESULTS_DIR = DATA_DIR / "results"
LOGS_DIR = DATA_DIR / "logs"
CACHE_DIR = DATA_DIR / "cache"
STATE_DIR = DATA_DIR / "state"
OUTBOX_DIR = DATA_DIR / "outbox"

for _d in (CONFIG_DIR, DATA_DIR, RESULTS_DIR, LOGS_DIR, CACHE_DIR, STATE_DIR, OUTBOX_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Load .env (real secrets). If missing we still start, but `check` will complain.
ENV_FILE = ROOT / ".env"
load_dotenv(ENV_FILE)


# --------------------------------------------------------------------------
# Small typed readers
# --------------------------------------------------------------------------
def _str(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _bool(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if raw == "":
        return default
    return raw in {"1", "true", "yes", "y", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int((os.getenv(name) or "").strip())
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float((os.getenv(name) or "").strip())
    except (TypeError, ValueError):
        return default


def _path(name: str, default: str) -> Path:
    raw = _str(name, default)
    p = Path(raw)
    return p if p.is_absolute() else (ROOT / p)


@dataclass(frozen=True)
class Settings:
    """All runtime settings, resolved once at import time."""

    # --- safety ---
    test_mode: bool = field(default_factory=lambda: _bool("TEST_MODE", True))
    require_approval: bool = field(default_factory=lambda: _bool("REQUIRE_APPROVAL", True))
    allow_real_sending: bool = field(default_factory=lambda: _bool("ALLOW_REAL_SENDING", False))
    follow_up_approval_required: bool = field(
        default_factory=lambda: _bool("FOLLOW_UP_APPROVAL_REQUIRED", True)
    )

    # --- limits ---
    max_companies_per_run: int = field(default_factory=lambda: _int("MAX_COMPANIES_PER_RUN", 1))
    send_rate_limit_seconds: int = field(default_factory=lambda: _int("SEND_RATE_LIMIT_SECONDS", 45))
    daily_send_limit: int = field(default_factory=lambda: _int("DAILY_SEND_LIMIT", 25))
    follow_up_days: int = field(default_factory=lambda: _int("FOLLOW_UP_DAYS", 7))
    duplicate_cooldown_days: int = field(
        default_factory=lambda: _int("DUPLICATE_COOLDOWN_DAYS", 90)
    )

    # --- BeviGrow tracker ---
    bevigrow_api_base: str = field(
        default_factory=lambda: _str(
            "BEVIGROW_API_BASE", "https://bevigrow-backend-dkay.onrender.com"
        ).rstrip("/")
    )
    bevigrow_email: str = field(default_factory=lambda: _str("BEVIGROW_EMAIL"))
    bevigrow_password: str = field(default_factory=lambda: _str("BEVIGROW_PASSWORD"))

    # --- Gmail ---
    gmail_sender: str = field(default_factory=lambda: _str("GMAIL_SENDER"))
    gmail_credentials_file: Path = field(
        default_factory=lambda: _path("GMAIL_CREDENTIALS_FILE", "config/gmail_credentials.json")
    )
    gmail_token_file: Path = field(
        default_factory=lambda: _path("GMAIL_TOKEN_FILE", "config/gmail_token.json")
    )
    outreach_bcc: str = field(default_factory=lambda: _str("OUTREACH_BCC"))

    # --- Claude ---
    anthropic_api_key: str = field(default_factory=lambda: _str("ANTHROPIC_API_KEY"))
    anthropic_model: str = field(default_factory=lambda: _str("ANTHROPIC_MODEL", "claude-opus-5"))
    anthropic_fast_model: str = field(
        default_factory=lambda: _str("ANTHROPIC_FAST_MODEL", "claude-sonnet-5")
    )
    llm_enabled: bool = field(default_factory=lambda: _bool("LLM_ENABLED", True))

    # --- search ---
    search_provider: str = field(default_factory=lambda: _str("SEARCH_PROVIDER", "auto").lower())
    tavily_api_key: str = field(default_factory=lambda: _str("TAVILY_API_KEY"))
    serper_api_key: str = field(default_factory=lambda: _str("SERPER_API_KEY"))

    # --- sender identity ---
    sender_name: str = field(default_factory=lambda: _str("SENDER_NAME"))
    sender_title: str = field(default_factory=lambda: _str("SENDER_TITLE"))
    sender_company: str = field(default_factory=lambda: _str("SENDER_COMPANY", "BeviGrow"))
    sender_phone: str = field(default_factory=lambda: _str("SENDER_PHONE"))
    sender_website: str = field(default_factory=lambda: _str("SENDER_WEBSITE"))
    sender_location: str = field(
        default_factory=lambda: _str("SENDER_LOCATION", "Yercaud, Tamil Nadu, India")
    )
    sender_linkedin: str = field(default_factory=lambda: _str("SENDER_LINKEDIN"))

    # --- crawler ---
    http_timeout_seconds: int = field(default_factory=lambda: _int("HTTP_TIMEOUT_SECONDS", 25))
    crawl_max_pages: int = field(default_factory=lambda: _int("CRAWL_MAX_PAGES", 12))
    crawl_delay_seconds: float = field(default_factory=lambda: _float("CRAWL_DELAY_SECONDS", 1.0))
    user_agent: str = field(
        default_factory=lambda: _str(
            "USER_AGENT",
            "BeviGrowOutreachBot/1.0 (+https://bevigrow.com; B2B green coffee enquiry)",
        )
    )
    respect_robots_txt: bool = field(default_factory=lambda: _bool("RESPECT_ROBOTS_TXT", True))

    # ----------------------------------------------------------------------
    # Derived helpers
    # ----------------------------------------------------------------------
    @property
    def llm_available(self) -> bool:
        return bool(self.llm_enabled and self.anthropic_api_key)

    @property
    def tracker_configured(self) -> bool:
        return bool(self.bevigrow_email and self.bevigrow_password)

    @property
    def gmail_configured(self) -> bool:
        return bool(self.gmail_sender and self.gmail_credentials_file.exists())

    @property
    def can_send_for_real(self) -> bool:
        """Both brakes must be released before a single real email can leave."""
        return (not self.test_mode) and self.allow_real_sending

    def missing_for(self, capability: str) -> list[str]:
        """Return a human-readable list of what is still missing for a capability."""
        missing: list[str] = []
        if capability == "tracker":
            if not self.bevigrow_email:
                missing.append("BEVIGROW_EMAIL in .env")
            if not self.bevigrow_password:
                missing.append("BEVIGROW_PASSWORD in .env")
        elif capability == "gmail":
            if not self.gmail_sender:
                missing.append("GMAIL_SENDER in .env")
            if not self.gmail_credentials_file.exists():
                missing.append(f"OAuth client file at {self.gmail_credentials_file}")
        elif capability == "llm":
            if not self.anthropic_api_key:
                missing.append("ANTHROPIC_API_KEY in .env")
        elif capability == "identity":
            if not self.sender_name:
                missing.append("SENDER_NAME in .env")
        return missing


settings = Settings()

# Paths exported for convenience
PATHS = {
    "root": ROOT,
    "config": CONFIG_DIR,
    "data": DATA_DIR,
    "results": RESULTS_DIR,
    "logs": LOGS_DIR,
    "cache": CACHE_DIR,
    "state": STATE_DIR,
    "outbox": OUTBOX_DIR,
}
