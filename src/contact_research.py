"""
Finding the right PERSON.

Preference order comes straight from the brief:
    Owner > Founder > Managing Director > Director > Purchasing Manager >
    Green Coffee Buyer > Coffee Buyer > Procurement > Sourcing > Import Manager

Two sources:
  * people Claude verified from public pages (each carries a source URL)
  * a conservative regex pass over crawled team / imprint pages

A person is only ever used if we saw their name published somewhere. Nothing
is ever constructed from a pattern.
"""

from __future__ import annotations

import re

from src.logging_setup import get_logger
from src.models import PersonCandidate

log = get_logger("contact_research")

# (regex on job title, score)
_TITLE_SCORES: list[tuple[str, int]] = [
    (r"green ?coffee (buyer|manager|trader)|rohkaffee", 100),
    (r"coffee buyer|kaffeeeink[äa]ufer|coffee (sourcing|procurement)", 95),
    (r"head of (purchasing|procurement|sourcing|buying)|einkaufsleit", 92),
    (r"(purchasing|procurement|sourcing|buying) (manager|director|lead|head)", 90),
    (r"import (manager|director)|importleit", 85),
    (r"\b(owner|inhaber|propriet[aà]rio|eigent[üu]mer|propriétaire)\b", 88),
    (r"\bfounder|gr[üu]nder|fondat", 86),
    (r"managing director|gesch[äa]ftsf[üu]hr|amministratore delegato|directeur g[ée]n[ée]ral|"
     r"\bmd\b|\bceo\b|chief executive", 84),
    (r"\bdirector\b|direktor|directeur|direttore", 70),
    (r"(supply chain|logistics) (manager|director)", 55),
    (r"(sales|commercial) (director|manager|head)|vertriebsleit", 50),
    (r"(quality|qc|qa) (manager|control)|q ?grader", 45),
    (r"roast(er|master)|r[öo]stmeister", 40),
    (r"partner|associate|manager", 30),
    # negatives
    (r"\bhr\b|human resources|recruit|personal(referent|abteilung)", -60),
    (r"marketing|social media|press|presse|communication", -35),
    (r"barista|shop (assistant|manager)|caf[ée] manager|intern|praktikant|apprentice", -50),
    (r"developer|engineer|it |web(master|design)", -60),
    (r"accountant|buchhalt|bookkeep", -40),
]

_NAME_RE = re.compile(
    r"\b([A-ZÄÖÜÅÆØÉÈÍÓÚÑ][a-zäöüßåæøéèíóúñ'’\-]{1,20}"
    r"(?:\s+(?:van|von|de|der|den|del|di|da|dos|la|le)\b)?"
    r"(?:\s+[A-ZÄÖÜÅÆØÉÈÍÓÚÑ][a-zäöüßåæøéèíóúñ'’\-]{1,25}){1,2})\b"
)

_TITLE_KEYWORDS = re.compile(
    r"(?i)(owner|inhaber|founder|gr[üu]nder|managing director|gesch[äa]ftsf[üu]hr|"
    r"\bceo\b|\bmd\b|director|direktor|directeur|purchasing|procurement|sourcing|"
    r"einkauf|import|buyer|eink[äa]ufer|head of|leiter|leitung|manager|trader|"
    r"partner|sales|vertrieb|quality|roaster|r[öo]stmeister)"
)

# Words that look like names but never are.
_NAME_BLOCKLIST = {
    "cookie policy", "privacy policy", "terms conditions", "all rights", "read more",
    "contact us", "our team", "green coffee", "coffee beans", "learn more", "sign up",
    "new york", "united kingdom", "united states", "value added", "quick links",
}


def score_title(title: str) -> int:
    t = (title or "").lower()
    if not t:
        return 10
    best = 0
    for pattern, points in _TITLE_SCORES:
        if re.search(pattern, t, re.I):
            best = points if abs(points) > abs(best) else best
            if points < 0:
                return points  # a disqualifying title wins immediately
    return best or 20


def _plausible_name(name: str) -> bool:
    low = name.lower().strip()
    if low in _NAME_BLOCKLIST or len(low) < 5 or len(low) > 45:
        return False
    if any(ch.isdigit() for ch in name):
        return False
    # A job title is not a person. "Sales Representative", "Quality
    # Coordinator" and "Green Coffee Buyer" all match the name pattern.
    if _TITLE_KEYWORDS.search(low):
        return False
    if re.search(
        r"(?i)\b(list|offer|team|group|company|coffee|kaffee|price|sample|order|contact|"
        r"about|home|news|blog|shop|login|menu|search|read|more|privacy|cookie|terms|"
        r"representative|coordinator|assistant|specialist|consultant|officer|executive)\b",
        low,
    ):
        return False
    parts = name.split()
    if parts and parts[0].lower() in {"our", "the", "a", "an", "my", "his", "her",
                                      "their", "meet", "with", "by", "from", "all"}:
        return False
    return 2 <= len(parts) <= 4


def people_from_pages(pages: list[tuple[str, str]]) -> list[PersonCandidate]:
    """
    Conservative regex pass: only accepts a name when a job-title keyword sits
    on the same line or the line immediately next to it.

    `pages` is a list of (url, text).
    """
    found: dict[str, PersonCandidate] = {}

    for url, text in pages:
        lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
        for i, line in enumerate(lines):
            if len(line) > 160:
                continue
            window = " | ".join(lines[max(0, i - 1) : i + 2])
            if not _TITLE_KEYWORDS.search(window):
                continue

            for match in _NAME_RE.findall(line):
                name = match.strip()
                if not _plausible_name(name):
                    continue
                # The title is the nearest line containing a title keyword.
                title = ""
                for candidate in (lines[i], *lines[max(0, i - 1) : i + 3]):
                    if candidate != name and _TITLE_KEYWORDS.search(candidate) and len(candidate) < 90:
                        title = candidate.replace(name, "").strip(" ,-–—|·:")
                        break
                key = name.lower()
                score = score_title(title)
                if score <= 0:
                    continue
                existing = found.get(key)
                if not existing or score > existing.score:
                    found[key] = PersonCandidate(
                        name=name,
                        title=title,
                        source_url=url,
                        score=score,
                        reason="name and job title published on the same page",
                    )

    people = sorted(found.values(), key=lambda p: -p.score)
    log.debug("Regex pass found %d candidate people", len(people))
    return people[:8]


def people_from_llm(entries: list[dict]) -> list[PersonCandidate]:
    """Turn Claude's verified people into candidates."""
    out: list[PersonCandidate] = []
    for entry in entries or []:
        name = (entry.get("name") or "").strip()
        if not name or not _plausible_name(name):
            continue
        title = (entry.get("title") or "").strip()
        confidence = (entry.get("confidence") or "low").lower()
        score = score_title(title) + {"high": 25, "medium": 10, "low": -10}.get(confidence, 0)
        if score <= 0:
            continue
        out.append(
            PersonCandidate(
                name=name,
                title=title,
                email=(entry.get("email") or "").strip().lower(),
                linkedin_url=(entry.get("source_url", "") if "linkedin.com" in
                              (entry.get("source_url") or "") else entry.get("linkedin_url") or ""),
                source_url=(entry.get("source_url") or "").strip(),
                score=score,
                reason=f"verified from a public source (confidence: {confidence})",
            )
        )
    return sorted(out, key=lambda p: -p.score)


def merge_people(*groups: list[PersonCandidate]) -> list[PersonCandidate]:
    """Combine sources, keeping the best-scored version of each person."""
    merged: dict[str, PersonCandidate] = {}
    for group in groups:
        for person in group:
            key = person.name.lower().strip()
            existing = merged.get(key)
            if not existing:
                merged[key] = person
                continue
            # Keep the richer record.
            if person.score > existing.score:
                person.email = person.email or existing.email
                person.linkedin_url = person.linkedin_url or existing.linkedin_url
                person.title = person.title or existing.title
                merged[key] = person
            else:
                existing.email = existing.email or person.email
                existing.linkedin_url = existing.linkedin_url or person.linkedin_url
                existing.title = existing.title or person.title
    return sorted(merged.values(), key=lambda p: -p.score)


def fallback_salutation(company_name: str) -> str:
    """Used when no person could be verified. Never invents a name."""
    core = re.sub(
        r"(?i)\s*(gmbh|ag|kg|ltd\.?|limited|llc|inc\.?|b\.?v\.?|n\.?v\.?|s\.?r\.?l\.?|"
        r"s\.?p\.?a\.?|s\.?a\.?s?\.?|oy|ab|a/s|aps|plc|pty|pte|&\s*co\.?)\b",
        "",
        company_name or "",
    ).strip(" ,.-&")
    return f"Dear {core} team," if core else "Dear Sir or Madam,"
