"""
Is this company worth contacting?

Two layers:
  * keyword rules (always run, no API key needed)
  * Claude's judgement (when available) - which wins when the two disagree,
    because it can read the actual page text

Never rejects a company just because information is thin - that becomes
UNCERTAIN and is flagged for you, exactly as the brief requires.
"""

from __future__ import annotations

import re

from src.models import Priority, Relevance

# (regex, points, human-readable signal)
_SIGNALS: list[tuple[str, int, str]] = [
    (r"green coffee|rohkaffee|gr[üu]ner kaffee|raw coffee|caf[ée] vert|caff[èe] verde|"
     r"gr[øo]nne kaffebonner|raakakahvi|r[åa]kaffe", 45, "mentions green coffee"),
    (r"\bimport(er|ing|s)?\b|einfuhr|importeur|importateur", 30, "imports"),
    (r"coffee import|kaffeeimport|green coffee import", 45, "green coffee importer"),
    (r"\broast(er|ery|ing|ers)\b|r[öo]ster|torref|brenneri|paahtimo|rosteri", 35, "roasts coffee"),
    (r"robusta", 35, "mentions Robusta"),
    (r"arabica", 15, "mentions Arabica"),
    (r"specialty coffee|spezialit[äa]tenkaffee|specialkaffe|erikoiskahvi", 25, "specialty coffee"),
    (r"wholesale|gro[ßs]handel|engros|tukku|b2b", 25, "wholesale / B2B"),
    (r"sourcing|procurement|purchasing|einkauf|beschaffung", 30, "has a sourcing function"),
    (r"\btrader?s?\b|handelshaus|trading (company|house)", 25, "trading house"),
    (r"origin|single origin|direct trade|producer relationship", 15, "origin sourcing language"),
    (r"\bindia\b|indian coffee|monsooned malabar|cherry ?ab", 25, "already engages with India"),
    (r"\bmt\b|metric ton|container|60 ?kg|jute bag|fcl|lcl", 20, "talks in trade volumes"),
    (r"warehouse|lager|silo|storage facility", 15, "has storage"),
    (r"cupping|qgrader|q ?grader|sca ", 12, "quality/cupping capability"),
    # negatives
    (r"we (are|re) an? (exporter|producer) of green coffee|coffee (estate|plantation) (in|of) "
     r"(brazil|vietnam|colombia|ethiopia|india|indonesia)", -60, "may be a competing exporter"),
    (r"permanently closed|out of business|geschlossen|company (has )?ceased", -80, "may be closed"),
    (r"coffee (machine|equipment|grinder)s? (repair|service|sales)", -25,
     "equipment business rather than beans"),
]

_NOT_COFFEE = re.compile(
    r"(?i)\b(coffee|kaffee|kahvi|kaffe|caf[ée]|caff[èe]|koffie|kava|kafa|cafea|espresso|bean)\b"
)


def rule_based(text: str, company_name: str = "") -> Relevance:
    """Score a company from its website text alone."""
    haystack = f"{company_name} {text}".lower()
    score = 0
    signals: list[str] = []

    for pattern, points, label in _SIGNALS:
        if re.search(pattern, haystack, re.I):
            score += points
            signals.append(label)

    if not haystack.strip():
        return Relevance(
            priority=Priority.UNCERTAIN,
            reason="No website text could be read, so relevance could not be judged.",
            signals=[],
        )

    if not _NOT_COFFEE.search(haystack):
        return Relevance(
            priority=Priority.UNCERTAIN,
            reason="Nothing on the site clearly identifies this as a coffee business.",
            signals=signals,
        )

    if score >= 110:
        priority = Priority.HIGH
    elif score >= 60:
        priority = Priority.MEDIUM
    elif score >= 25:
        priority = Priority.LOW
    elif score < 0:
        priority = Priority.IRRELEVANT
    else:
        priority = Priority.UNCERTAIN

    return Relevance(
        priority=priority,
        reason=f"Keyword score {score}. " + ("; ".join(signals[:6]) or "few relevant signals."),
        signals=signals,
    )


def from_llm(facts: dict) -> Relevance:
    """Build a Relevance from Claude's structured verdict."""
    raw = (facts.get("priority") or "UNCERTAIN").strip().upper()
    try:
        priority = Priority(raw)
    except ValueError:
        priority = Priority.UNCERTAIN

    signals = [s for s in (facts.get("signals") or []) if isinstance(s, str)]
    extra = []
    if facts.get("business_type") and facts["business_type"] != "unknown":
        extra.append(f"type: {facts['business_type']}")
    if facts.get("buys_green_coffee") and facts["buys_green_coffee"] != "unknown":
        extra.append(f"buys green coffee: {facts['buys_green_coffee']}")

    return Relevance(
        priority=priority,
        reason=(facts.get("priority_reason") or "").strip() or "No reason given.",
        signals=signals + extra,
    )


def combine(rules: Relevance, llm: Relevance | None) -> Relevance:
    """
    Claude's verdict wins, because it read the real page text - except that a
    strong negative rule signal is never silently overruled.
    """
    if llm is None:
        return rules

    negative = {"may be a competing exporter", "may be closed"}
    blockers = [s for s in rules.signals if s in negative]

    merged_signals = list(dict.fromkeys(llm.signals + rules.signals))

    if blockers and llm.priority in (Priority.HIGH, Priority.MEDIUM):
        return Relevance(
            priority=Priority.UNCERTAIN,
            reason=(
                f"{llm.reason} BUT the website also suggests: {', '.join(blockers)}. "
                "Please check before contacting."
            ),
            signals=merged_signals,
        )

    return Relevance(priority=llm.priority, reason=llm.reason, signals=merged_signals)


def should_contact(relevance: Relevance) -> tuple[bool, str]:
    """Gate before we spend effort preparing a message."""
    if relevance.priority is Priority.IRRELEVANT:
        return False, f"Classified IRRELEVANT: {relevance.reason}"
    return True, ""
