"""
Web search - used to find a company's official website when we don't have it.

Three providers, tried in this order:
  1. Tavily   (TAVILY_API_KEY)   - best quality, free tier
  2. Serper   (SERPER_API_KEY)   - Google results
  3. DuckDuckGo HTML             - no key, best-effort fallback

If none work, research continues without search - the pipeline just relies on
the website column in your input file or on Claude's own web search.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup

from src.config import settings
from src.logging_setup import get_logger
from src.utils import domain_of, http_session, normalise_url

log = get_logger("search")


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str = ""
    provider: str = ""


# Domains that are never a company's own website.
_NON_OFFICIAL = {
    "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "youtube.com", "wikipedia.org", "crunchbase.com", "bloomberg.com",
    "dnb.com", "opencorporates.com", "yelp.com", "tripadvisor.com",
    "indeed.com", "glassdoor.com", "zoominfo.com", "apollo.io", "rocketreach.co",
    "northdata.com", "companieshouse.gov.uk", "kompass.com", "europages.co.uk",
    "europages.com", "yellowpages.com", "gelbeseiten.de", "pinterest.com",
    "tiktok.com", "medium.com", "reddit.com", "amazon.com", "ebay.com",
    "google.com", "bing.com", "duckduckgo.com", "trustpilot.com", "yumpu.com",
    # company registries / insolvency notices / trade press - never a homepage
    "companyhouse.de", "insolvenz-radar.de", "unternehmensregister.de",
    "bundesanzeiger.de", "firmenwissen.de", "wer-zu-wem.de", "moneyhouse.ch",
    "creditreform.de", "implisense.com", "companywall.com", "bizapedia.com",
    "dailycoffeenews.com", "perfectdailygrind.com", "globalcoffeereport.com",
    "handelsblatt.com", "abendblatt.de", "mopo.de", "welt.de", "faz.net",
    "sueddeutsche.de", "spiegel.de", "wikiwand.com", "facebook.net",
}


def is_official_candidate(url: str) -> bool:
    d = domain_of(url)
    if not d:
        return False
    return not any(d == bad or d.endswith("." + bad) for bad in _NON_OFFICIAL)


# --------------------------------------------------------------------------
# Providers
# --------------------------------------------------------------------------
def _tavily(query: str, limit: int) -> list[SearchHit]:
    resp = http_session().post(
        "https://api.tavily.com/search",
        json={
            "api_key": settings.tavily_api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": limit,
            "include_answer": False,
        },
        timeout=settings.http_timeout_seconds,
    )
    resp.raise_for_status()
    return [
        SearchHit(
            title=r.get("title", ""),
            url=r.get("url", ""),
            snippet=r.get("content", "")[:400],
            provider="tavily",
        )
        for r in resp.json().get("results", [])
    ]


def _serper(query: str, limit: int) -> list[SearchHit]:
    resp = http_session().post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
        json={"q": query, "num": limit},
        timeout=settings.http_timeout_seconds,
    )
    resp.raise_for_status()
    data = resp.json()
    hits: list[SearchHit] = []
    if isinstance(data.get("knowledgeGraph"), dict):
        kg = data["knowledgeGraph"]
        if kg.get("website"):
            hits.append(
                SearchHit(
                    title=kg.get("title", ""),
                    url=kg["website"],
                    snippet=kg.get("description", ""),
                    provider="serper-kg",
                )
            )
    for r in data.get("organic", [])[:limit]:
        hits.append(
            SearchHit(
                title=r.get("title", ""),
                url=r.get("link", ""),
                snippet=r.get("snippet", ""),
                provider="serper",
            )
        )
    return hits


# A search engine will not answer a self-identified bot, so search requests
# (and ONLY search requests) go out with an ordinary browser user agent.
# Company websites are still crawled with the honest BeviGrow user agent.
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _unwrap(href: str) -> str:
    """DuckDuckGo sometimes wraps results as /l/?uddg=<encoded url>."""
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    if "duckduckgo.com/l/" in href or href.startswith("/l/?"):
        qs = parse_qs(urlparse(href).query)
        return unquote(qs.get("uddg", [""])[0])
    return href


def _duckduckgo(query: str, limit: int) -> list[SearchHit]:
    headers = {
        "User-Agent": _BROWSER_UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-GB,en;q=0.9,de;q=0.7",
        "Referer": "https://duckduckgo.com/",
    }
    hits: list[SearchHit] = []

    for endpoint, link_sel, snippet_sel in (
        ("https://html.duckduckgo.com/html/", "a.result__a", ".result__snippet"),
        ("https://lite.duckduckgo.com/lite/", "a.result-link", ".result-snippet"),
    ):
        try:
            resp = http_session().post(
                endpoint, data={"q": query}, headers=headers,
                timeout=settings.http_timeout_seconds,
            )
        except Exception:
            continue
        if resp.status_code != 200:
            continue

        soup = BeautifulSoup(resp.text, "lxml")
        for link in soup.select(link_sel):
            url = _unwrap(link.get("href", ""))
            if not url or not url.startswith("http"):
                continue
            parent = link.find_parent(["div", "tr", "table"]) or link
            snippet_node = parent.select_one(snippet_sel) if snippet_sel else None
            hits.append(
                SearchHit(
                    title=link.get_text(" ", strip=True),
                    url=url,
                    snippet=snippet_node.get_text(" ", strip=True) if snippet_node else "",
                    provider="duckduckgo",
                )
            )
            if len(hits) >= limit:
                return hits
        if hits:
            return hits
    return hits


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def available_provider() -> str:
    choice = settings.search_provider
    if choice == "tavily" and settings.tavily_api_key:
        return "tavily"
    if choice == "serper" and settings.serper_api_key:
        return "serper"
    if choice == "duckduckgo":
        return "duckduckgo"
    if settings.tavily_api_key:
        return "tavily"
    if settings.serper_api_key:
        return "serper"
    return "duckduckgo"


def search(query: str, limit: int = 8) -> list[SearchHit]:
    """Run one search. Never raises - returns [] if every provider fails."""
    order = [available_provider()]
    for fallback in ("tavily", "serper", "duckduckgo"):
        if fallback not in order:
            order.append(fallback)

    for provider in order:
        try:
            if provider == "tavily" and not settings.tavily_api_key:
                continue
            if provider == "serper" and not settings.serper_api_key:
                continue

            fn = {"tavily": _tavily, "serper": _serper, "duckduckgo": _duckduckgo}[provider]
            hits = [h for h in fn(query, limit) if h.url]
            if hits:
                log.debug("search(%s) via %s -> %d hits", query, provider, len(hits))
                return hits
        except Exception as exc:
            log.debug("Search provider %s failed: %s", provider, exc)
            continue

    log.warning("No search results for: %s", query)
    return []


def find_official_website(company: str, city: str = "", country: str = "") -> tuple[str, str, str]:
    """
    Find the company's own website.

    Returns (url, source_url, how) - empty url means "not confidently found".
    """
    place = " ".join(p for p in (city, country) if p)
    queries = [
        f'"{company}" {place} official website'.strip(),
        f"{company} {place} coffee".strip(),
        f"{company} contact".strip(),
    ]

    scored: dict[str, tuple[int, SearchHit]] = {}
    company_tokens = {t for t in re.sub(r"[^a-z0-9 ]", " ", company.lower()).split() if len(t) > 2}

    for query in queries:
        for rank, hit in enumerate(search(query, limit=8)):
            if not is_official_candidate(hit.url):
                continue
            d = domain_of(hit.url)
            if not d:
                continue

            score = max(0, 20 - rank * 2)
            domain_core = re.sub(r"[^a-z0-9]", "", d.split(".")[0])
            # Big boost when the domain literally contains part of the name.
            for token in company_tokens:
                if token in domain_core:
                    score += 25
                    break
            haystack = f"{hit.title} {hit.snippet}".lower()
            score += 5 * sum(1 for t in company_tokens if t in haystack)
            if country and country.lower() in haystack:
                score += 3

            best = scored.get(d)
            if not best or score > best[0]:
                scored[d] = (score, hit)

        if scored and max(v[0] for v in scored.values()) >= 30:
            break  # confident enough, stop burning search quota

    if not scored:
        return "", "", ""

    score, winner = max(scored.values(), key=lambda item: item[0])
    # Below this, the "best" hit is usually a news article or a directory page
    # that merely mentions the company. Better to report nothing than a wrong
    # website, because everything downstream depends on it.
    if score < 25:
        log.info(
            "Best website candidate for '%s' was only %s (score %d) - not confident enough.",
            company, winner.url, score,
        )
        return "", "", ""

    return (
        normalise_url(f"https://{domain_of(winner.url)}"),
        winner.url,
        f"web search ({winner.provider})",
    )


def find_linkedin(company: str, country: str = "") -> str:
    """Best-effort LinkedIn company page URL. Read-only search, no scraping."""
    for hit in search(f'"{company}" {country} linkedin company'.strip(), limit=6):
        if "linkedin.com/company/" in hit.url.lower():
            return hit.url.split("?")[0]
    return ""
