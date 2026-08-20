"""
Website crawler - the evidence gatherer.

This is the part of the system that produces *facts with a source URL*.
It visits a company's own website (only their own domain), follows a handful
of pages that normally carry contact details, and pulls out:

    emails, people, LinkedIn links, phone numbers, contact pages, forms

It is deliberately polite: it obeys robots.txt, waits between requests, sends
an honest user agent, and never visits more pages than CRAWL_MAX_PAGES.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup

from src.config import CACHE_DIR, settings
from src.logging_setup import get_logger
from src.utils import (
    absolute_url,
    deobfuscate,
    domain_of,
    extract_emails,
    http_session,
    looks_like_email,
    normalise_url,
    polite_sleep,
    read_json,
    same_domain,
    sha256,
    write_json,
)

log = get_logger("crawler")

# Pages worth visiting, in priority order. Multilingual because the prospect
# list is European.
_PAGE_HINTS: list[tuple[str, int]] = [
    # (substring found in href or link text, priority - higher is visited first)
    ("contact", 100), ("kontakt", 100), ("contatti", 95), ("contacto", 95),
    ("contactez", 95), ("nous-contacter", 95), ("yhteystiedot", 95), ("kontakta", 95),
    ("impressum", 90), ("imprint", 90), ("legal-notice", 85), ("mentions-legales", 85),
    ("about", 70), ("ueber-uns", 70), ("uber-uns", 70), ("om-oss", 70), ("chi-siamo", 70),
    ("team", 75), ("people", 70), ("staff", 70), ("management", 72), ("leadership", 72),
    ("who-we-are", 68), ("our-story", 60),
    ("green-coffee", 80), ("gruener-kaffee", 80), ("rohkaffee", 80), ("raw-coffee", 78),
    ("sourcing", 78), ("purchasing", 82), ("procurement", 82), ("einkauf", 82),
    ("wholesale", 76), ("b2b", 76), ("trade", 70), ("import", 74), ("supplier", 74),
    ("partners", 60), ("company", 55), ("firma", 55), ("enquiry", 85), ("inquiry", 85),
]

_SKIP_URL_PATTERNS = re.compile(
    r"(?i)\.(pdf|jpe?g|png|gif|webp|svg|zip|mp4|mp3|docx?|xlsx?|pptx?|css|js)(\?|$)"
    r"|/(cart|checkout|basket|login|signin|account|wp-admin|wp-json|feed|tag|author)/"
    r"|[?&](add-to-cart|replytocom)="
)

_PHONE_RE = re.compile(r"\+\d[\d\s().\-]{7,20}\d")


@dataclass
class Page:
    url: str
    status: int
    html: str = ""
    text: str = ""
    title: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status == 200 and bool(self.html)


@dataclass
class SiteEvidence:
    """Everything the crawler found on one website."""

    base_url: str = ""
    pages: list[Page] = field(default_factory=list)
    emails: dict[str, str] = field(default_factory=dict)      # address -> source url
    linkedin_urls: dict[str, str] = field(default_factory=dict)  # url -> source url
    phones: dict[str, str] = field(default_factory=dict)
    contact_page_url: str = ""
    form_pages: list[str] = field(default_factory=list)
    title: str = ""
    meta_description: str = ""
    reachable: bool = False
    error: str = ""

    def combined_text(self, limit: int = 24000) -> str:
        """Readable text from every crawled page, for the reasoning step."""
        chunks: list[str] = []
        for page in self.pages:
            if not page.text:
                continue
            chunks.append(f"\n### PAGE: {page.url}\n{page.text[:6000]}")
        return "\n".join(chunks)[:limit]


# --------------------------------------------------------------------------
# robots.txt
# --------------------------------------------------------------------------
_robots_cache: dict[str, RobotFileParser | None] = {}


def _robots_allows(url: str) -> bool:
    if not settings.respect_robots_txt:
        return True
    host = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    if host not in _robots_cache:
        parser: RobotFileParser | None = RobotFileParser()
        try:
            resp = http_session().get(f"{host}/robots.txt", timeout=10)
            if resp.status_code == 200 and len(resp.text) < 500_000:
                parser.parse(resp.text.splitlines())
            else:
                parser = None  # no usable robots.txt -> allow
        except Exception:
            parser = None
        _robots_cache[host] = parser

    parser = _robots_cache[host]
    if parser is None:
        return True
    try:
        return parser.can_fetch(settings.user_agent, url)
    except Exception:
        return True


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------
def fetch(url: str, use_cache: bool = True) -> Page:
    """Fetch one page, with an on-disk cache so re-runs are fast and polite."""
    url = normalise_url(url)
    cache_file = CACHE_DIR / f"page-{sha256(url)[:24]}.json"

    if use_cache:
        cached = read_json(cache_file)
        if cached and time.time() - cached.get("_cached_at", 0) < 60 * 60 * 24 * 7:
            return Page(
                url=cached["url"],
                status=cached["status"],
                html=cached.get("html", ""),
                text=cached.get("text", ""),
                title=cached.get("title", ""),
                error=cached.get("error", ""),
            )

    if not _robots_allows(url):
        log.info("robots.txt disallows %s - skipping", url)
        return Page(url=url, status=0, error="blocked by robots.txt")

    try:
        resp = http_session().get(
            url, timeout=settings.http_timeout_seconds, allow_redirects=True
        )
        content_type = resp.headers.get("Content-Type", "")
        if "html" not in content_type.lower() and resp.status_code == 200:
            page = Page(url=resp.url, status=resp.status_code, error=f"not html ({content_type})")
        else:
            html = resp.text[:1_500_000]
            soup = BeautifulSoup(html, "lxml")
            for tag in soup(["script", "style", "noscript", "svg"]):
                tag.decompose()
            text = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True))
            title = soup.title.get_text(strip=True) if soup.title else ""
            page = Page(url=resp.url, status=resp.status_code, html=html, text=text, title=title)
    except Exception as exc:
        page = Page(url=url, status=0, error=str(exc)[:200])

    write_json(
        cache_file,
        {
            "url": page.url,
            "status": page.status,
            "html": page.html,
            "text": page.text,
            "title": page.title,
            "error": page.error,
            "_cached_at": time.time(),
        },
    )
    polite_sleep(settings.crawl_delay_seconds)
    return page


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------
def _emails_from_page(page: Page) -> list[str]:
    """mailto: links first (highest confidence), then visible text."""
    found: list[str] = []
    soup = BeautifulSoup(page.html, "lxml")

    for a in soup.select('a[href^="mailto:"]'):
        raw = (a.get("href") or "")[7:].split("?")[0]
        addr = raw.strip().lower()
        if looks_like_email(addr) and addr not in found:
            found.append(addr)

    # Visible text, including "info (at) company (dot) com" spellings.
    for addr in extract_emails(deobfuscate(page.text)):
        if addr not in found:
            found.append(addr)

    # Cloudflare-protected addresses are encoded; decode them rather than guess.
    for node in soup.select("[data-cfemail]"):
        decoded = _decode_cfemail(node.get("data-cfemail", ""))
        if decoded and decoded not in found:
            found.append(decoded)

    return found


def _decode_cfemail(encoded: str) -> str:
    """Undo Cloudflare's simple email obfuscation."""
    try:
        key = int(encoded[:2], 16)
        decoded = "".join(
            chr(int(encoded[i : i + 2], 16) ^ key) for i in range(2, len(encoded), 2)
        )
        return decoded.lower() if looks_like_email(decoded) else ""
    except Exception:
        return ""


def _linkedin_from_page(page: Page) -> list[str]:
    urls: list[str] = []
    for match in re.findall(
        r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:company|in|school)/[A-Za-z0-9_\-%.]+",
        page.html,
        re.I,
    ):
        clean = match.split("?")[0].rstrip("/")
        if clean not in urls:
            urls.append(clean)
    return urls


def _has_contact_form(page: Page) -> bool:
    soup = BeautifulSoup(page.html, "lxml")
    for form in soup.find_all("form"):
        inputs = form.find_all(["input", "textarea", "select"])
        types = {(i.get("type") or i.name or "").lower() for i in inputs}
        names = " ".join((i.get("name") or "") + " " + (i.get("id") or "") for i in inputs).lower()
        looks_like_search = "search" in names and len(inputs) <= 2
        has_message = "textarea" in types or "message" in names or "nachricht" in names
        has_email = "email" in types or "email" in names or "mail" in names
        if has_message and has_email and not looks_like_search:
            return True
    # Embedded form builders (Typeform, HubSpot, Jotform, Wufoo...)
    return bool(
        re.search(
            r"(?i)(typeform\.com|hsforms\.net|jotform|wufoo|formstack|gravity_?forms|wpcf7|contact-form-7)",
            page.html,
        )
    )


def _candidate_links(page: Page, base_domain: str) -> list[tuple[int, str]]:
    """Rank internal links by how likely they are to hold contact details."""
    soup = BeautifulSoup(page.html, "lxml")
    ranked: dict[str, int] = {}

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        url = absolute_url(page.url, href)
        if not url or not same_domain(url, base_domain):
            continue
        if _SKIP_URL_PATTERNS.search(url):
            continue

        haystack = (url + " " + a.get_text(" ", strip=True)).lower()
        best = 0
        for hint, priority in _PAGE_HINTS:
            if hint in haystack:
                best = max(best, priority)
        if best:
            clean = url.split("#")[0].rstrip("/")
            ranked[clean] = max(ranked.get(clean, 0), best)

    return sorted(((p, u) for u, p in ranked.items()), reverse=True)


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------
def crawl_site(website: str, max_pages: int | None = None) -> SiteEvidence:
    """Crawl a company website and collect contact evidence."""
    evidence = SiteEvidence(base_url=normalise_url(website))
    if not evidence.base_url:
        evidence.error = "no website URL"
        return evidence

    max_pages = max_pages or settings.crawl_max_pages
    base_domain = domain_of(evidence.base_url)

    home = fetch(evidence.base_url)
    if not home.ok:
        # Try the other spelling of the host before giving up.
        alt = (
            evidence.base_url.replace("://www.", "://")
            if "://www." in evidence.base_url
            else evidence.base_url.replace("://", "://www.")
        )
        home = fetch(alt)
        if home.ok:
            evidence.base_url = normalise_url(home.url)
            base_domain = domain_of(evidence.base_url)

    if not home.ok:
        evidence.error = home.error or f"HTTP {home.status}"
        log.warning("Website unreachable: %s (%s)", website, evidence.error)
        return evidence

    evidence.reachable = True
    evidence.title = home.title
    soup = BeautifulSoup(home.html, "lxml")
    meta = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    evidence.meta_description = (meta.get("content") or "").strip() if meta else ""

    visited: set[str] = set()
    queue: list[tuple[int, str]] = [(1000, evidence.base_url)]
    queue.extend(_candidate_links(home, base_domain))

    while queue and len(visited) < max_pages:
        queue.sort(reverse=True)
        _, url = queue.pop(0)
        key = url.split("#")[0].rstrip("/")
        if key in visited:
            continue
        visited.add(key)

        page = home if key == evidence.base_url.rstrip("/") else fetch(url)
        if not page.ok:
            continue
        evidence.pages.append(page)

        for addr in _emails_from_page(page):
            evidence.emails.setdefault(addr, page.url)
        for li in _linkedin_from_page(page):
            evidence.linkedin_urls.setdefault(li, page.url)
        for phone in _PHONE_RE.findall(page.text)[:3]:
            evidence.phones.setdefault(re.sub(r"[^\d+]", "", phone), page.url)

        lowered = page.url.lower()
        if not evidence.contact_page_url and any(
            h in lowered for h in ("contact", "kontakt", "contatti", "contacto", "enquiry")
        ):
            evidence.contact_page_url = page.url

        if _has_contact_form(page) and page.url not in evidence.form_pages:
            evidence.form_pages.append(page.url)

        # A contact page often links to the team page - keep discovering.
        if len(visited) < max_pages:
            for priority, link in _candidate_links(page, base_domain):
                if link.split("#")[0].rstrip("/") not in visited:
                    queue.append((priority - 5, link))

    if not evidence.contact_page_url and evidence.form_pages:
        evidence.contact_page_url = evidence.form_pages[0]

    log.info(
        "Crawled %s: %d pages, %d emails, %d LinkedIn links, %d form pages",
        base_domain,
        len(evidence.pages),
        len(evidence.emails),
        len(evidence.linkedin_urls),
        len(evidence.form_pages),
    )
    return evidence
