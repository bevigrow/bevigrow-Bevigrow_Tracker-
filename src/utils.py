"""
Shared helpers: HTTP session, JSON files, email/URL handling, name matching.

Nothing here talks to a third-party API - it is all local plumbing.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import settings

# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------
_session: requests.Session | None = None


def http_session() -> requests.Session:
    """A requests session with retries, a polite user agent and sane timeouts."""
    global _session
    if _session is not None:
        return _session

    s = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=2,
        backoff_factor=1.2,
        status_forcelist=(408, 429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD", "POST"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update(
        {
            "User-Agent": settings.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9,de;q=0.6",
        }
    )
    _session = s
    return s


# --------------------------------------------------------------------------
# JSON files
# --------------------------------------------------------------------------
def read_json(path: Path, default: Any = None) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, default=str)
    tmp.replace(path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def read_text(path: Path, default: str = "") -> str:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return default


# --------------------------------------------------------------------------
# Text / names
# --------------------------------------------------------------------------
_LEGAL_SUFFIXES = {
    "gmbh", "co", "kg", "ag", "ltd", "limited", "llc", "inc", "incorporated",
    "bv", "b.v.", "nv", "n.v.", "srl", "s.r.l", "spa", "s.p.a", "sa", "s.a",
    "sas", "sarl", "oy", "ab", "as", "a/s", "aps", "plc", "pty", "pte",
    "gbr", "ohg", "ug", "ek", "e.k", "kft", "sp", "z.o.o", "zoo", "doo",
    "corp", "corporation", "company", "the", "and", "und", "og",
}


def slugify(text: str, max_len: int = 60) -> str:
    """Filesystem-safe identifier."""
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return (text or "unknown")[:max_len]


def normalise_company_name(name: str) -> str:
    """
    Reduce a company name to a comparable core.

    "Benecke Coffee GmbH & Co. KG" -> "benecke coffee"
    Used for duplicate detection, never for display.
    """
    name = unicodedata.normalize("NFKD", name or "")
    name = name.encode("ascii", "ignore").decode("ascii").lower()
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    words = [w for w in name.split() if w and w not in _LEGAL_SUFFIXES]
    return " ".join(words).strip()


def company_key(name: str) -> str:
    """Stable key for a company, used in the local state files."""
    return normalise_company_name(name).replace(" ", "-") or slugify(name)


def similar(a: str, b: str) -> float:
    """Cheap token-overlap similarity between two normalised company names."""
    ta = set(normalise_company_name(a).split())
    tb = set(normalise_company_name(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def truncate(text: str, limit: int = 400) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# URLs
# --------------------------------------------------------------------------
def normalise_url(url: str) -> str:
    """Add a scheme if missing, strip fragments and tracking noise."""
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url.lstrip("/")
    parsed = urlparse(url)
    path = parsed.path or "/"
    rebuilt = f"{parsed.scheme}://{parsed.netloc}{path}"
    if parsed.query:
        rebuilt += f"?{parsed.query}"
    return rebuilt.rstrip("/") if path == "/" else rebuilt


def domain_of(url_or_email: str) -> str:
    """Registrable-ish domain, lowercase, without 'www.'."""
    value = (url_or_email or "").strip().lower()
    if not value:
        return ""
    if "@" in value and "://" not in value:
        return value.split("@")[-1].strip().strip(">").strip(".")
    if "://" not in value:
        value = "https://" + value
    host = urlparse(value).netloc
    host = host.split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def same_domain(a: str, b: str) -> bool:
    da, db = domain_of(a), domain_of(b)
    if not da or not db:
        return False
    return da == db or da.endswith("." + db) or db.endswith("." + da)


def absolute_url(base: str, href: str) -> str:
    try:
        return urljoin(base, (href or "").strip())
    except Exception:
        return ""


# --------------------------------------------------------------------------
# Emails
# --------------------------------------------------------------------------
EMAIL_RE = re.compile(
    r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~.\-]+@[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?)+"
)

# Addresses that are almost never a real human inbox.
_JUNK_EMAIL_PATTERNS = (
    "example.com", "example.org", "yourdomain", "domain.com", "email.com",
    "sentry.io", "wixpress.com", "godaddy", "squarespace", "shopify",
    "@2x.png", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js",
    "u003e", "sentry-next", "no-reply@", "noreply@", "donotreply@",
)


def looks_like_email(value: str) -> bool:
    value = (value or "").strip().lower()
    if not value or value.count("@") != 1:
        return False
    if not EMAIL_RE.fullmatch(value):
        return False
    if len(value) > 254:
        return False
    local, _, dom = value.partition("@")
    if not local or local.startswith(".") or local.endswith("."):
        return False
    if ".." in value:
        return False
    tld = dom.rsplit(".", 1)[-1]
    if not tld.isalpha() or len(tld) < 2:
        return False
    return not any(junk in value for junk in _JUNK_EMAIL_PATTERNS)


def extract_emails(text: str) -> list[str]:
    """Pull every plausible email address out of a blob of text/HTML."""
    found: list[str] = []
    for raw in EMAIL_RE.findall(text or ""):
        addr = raw.strip().strip(".,;:)('\"<>").lower()
        if looks_like_email(addr) and addr not in found:
            found.append(addr)
    return found


def deobfuscate(text: str) -> str:
    """
    Turn common anti-scraping spellings back into real addresses:
        "info (at) company (dot) com"  ->  "info@company.com"
    Only applied to visible page text, never to code.
    """
    if not text:
        return ""
    out = text
    out = re.sub(r"\s*[\(\[\{]\s*(?:at|@|AT)\s*[\)\]\}]\s*", "@", out)
    out = re.sub(r"\s+(?:at)\s+(?=[A-Za-z0-9\-]+\s+(?:dot|\.)\s)", "@", out)
    out = re.sub(r"\s*[\(\[\{]\s*(?:dot|punkt|DOT)\s*[\)\]\}]\s*", ".", out)
    out = re.sub(r"\s+(?:dot|punkt)\s+", ".", out)
    return out


def mx_records_exist(domain: str) -> bool | None:
    """
    True/False if we could check, None if dnspython is unavailable or DNS failed.
    Used to catch typo'd or dead domains before we waste a send.
    """
    if not domain:
        return False
    try:
        import dns.resolver  # type: ignore

        resolver = dns.resolver.Resolver()
        resolver.lifetime = 6.0
        resolver.timeout = 3.0
        answers = resolver.resolve(domain, "MX")
        return len(answers) > 0
    except ImportError:
        return None
    except Exception:
        # NXDOMAIN / NoAnswer / timeout -> treat as "no mail server found"
        try:
            import dns.resolver  # type: ignore

            dns.resolver.resolve(domain, "A")
            return None  # host exists but no MX record we could read
        except Exception:
            return False


# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------
def today() -> date:
    return date.today()


def iso(d: date | datetime | None) -> str:
    if d is None:
        return ""
    if isinstance(d, datetime):
        return d.date().isoformat()
    return d.isoformat()


def days_from_now(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(value)[:10], fmt).date()
        except ValueError:
            continue
    return None


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Misc
# --------------------------------------------------------------------------
def unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = (item or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(item.strip())
    return out


def polite_sleep(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)
