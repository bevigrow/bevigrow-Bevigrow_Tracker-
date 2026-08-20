"""
Choosing WHICH email address to write to.

The rule from the brief: never just take the first address you find. Score
every address by how likely it is to reach someone who buys green coffee, and
flag the company for review when nothing is clearly right.
"""

from __future__ import annotations

import re

from src.config import settings
from src.logging_setup import get_logger
from src.models import EmailCandidate
from src.utils import domain_of, looks_like_email, mx_records_exist, same_domain

log = get_logger("email_finder")

# (regex on the part before @, score, category, why)
_RULES: list[tuple[str, int, str, str]] = [
    # --- best: people who actually buy coffee ---
    (r"^(green ?coffee|rohkaffee|gruenerkaffee|raw ?coffee|coffeebuying|kaffeeeinkauf)", 100,
     "green coffee", "green coffee desk"),
    (r"^(purchas|procure|procurement|einkauf|inkoop|achat|acquisti|compras|indkob|inkop)", 95,
     "purchasing", "purchasing / procurement"),
    (r"^(sourcing|supply|supplier|beschaffung|import|imports)", 90,
     "sourcing", "sourcing / import"),
    (r"^(buyer|buying|coffeebuyer|traders?|trading|trade)", 85,
     "trading", "trading / buying"),
    # --- good: commercial routes ---
    (r"^(sales|vertrieb|ventas|vendite|myynti|salg|commercial|business|bd)", 70,
     "sales", "sales / commercial"),
    (r"^(wholesale|b2b|grosshandel|horeca)", 68, "wholesale", "wholesale / B2B"),
    (r"^(management|geschaeftsfuehrung|direction|direzione|md|ceo|owner|founder|inhaber)", 72,
     "management", "management / owner"),
    (r"^(quality|qualitaet|qc|qa|lab)", 45, "quality", "quality department"),
    # --- acceptable general inboxes ---
    (r"^(hello|hallo|hei|hej|hola|ciao|bonjour|moin)", 55, "general", "general greeting inbox"),
    (r"^(info|office|mail|contact|kontakt|enquir|inquir|anfrage|post|kontor)", 52,
     "general", "general company inbox"),
    (r"^(admin|administration|verwaltung|buero|bureau)", 40, "general", "administration"),
    (r"^(accounts?|buchhaltung|finance|rechnung|invoice|billing|debitor)", 15,
     "finance", "finance - rarely the right route"),
    # --- avoid unless nothing else exists ---
    (r"^(jobs?|career|karriere|hr|recruit|bewerbung|personal|apply)", -60,
     "avoid", "HR / careers"),
    (r"^(support|help|helpdesk|service|kundenservice|customercare|technical|it|webmaster|hostmaster|postmaster|abuse)",
     -50, "avoid", "support / technical"),
    (r"^(press|presse|media|marketing|pr|newsletter|social|shop|webshop|store|order|bestellung)",
     -35, "avoid", "press / marketing / retail shop"),
    (r"^(privacy|datenschutz|dpo|gdpr|legal|recht|compliance)", -45, "avoid", "legal / privacy"),
    (r"^(no-?reply|do-?not-?reply|donotreply|bounce|mailer-daemon|automated)", -100,
     "avoid", "automated mailbox"),
]

# Free mailbox providers - fine for a micro-roaster, but worth noting.
_FREE_PROVIDERS = {
    "gmail.com", "googlemail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "live.com", "gmx.de", "gmx.net", "web.de", "t-online.de", "aol.com",
    "icloud.com", "me.com", "mail.ru", "yandex.ru", "protonmail.com", "proton.me",
}


def _classify(address: str) -> tuple[int, str, str]:
    local = address.split("@")[0].lower()
    local_clean = re.sub(r"[^a-z]", "", local)

    for pattern, score, category, reason in _RULES:
        if re.match(pattern, local) or re.match(pattern, local_clean):
            return score, category, reason

    # A mailbox literally named after the product is a buying desk.
    if re.fullmatch(r"(coffee|kaffee|kahvi|kaffe|cafe|beans?|bohnen)", local_clean):
        return 75, "green coffee", "mailbox named after coffee itself"

    # firstname.lastname@ - a named person, usually good if we know their role.
    if re.match(r"^[a-z]+[._\-][a-z]+$", local):
        return 60, "person", "looks like a named person"
    # firstname@ - very common at small roasters and importers.
    if re.fullmatch(r"[a-z]{3,14}", local_clean):
        return 50, "person", "looks like an individual's mailbox"
    if len(local_clean) <= 3:
        return 35, "unknown", "short/initial mailbox"
    return 45, "unknown", "unrecognised mailbox name"


def score_emails(
    raw_emails: dict[str, str],
    website: str,
    check_mx: bool = True,
) -> list[EmailCandidate]:
    """
    Turn {address: source_url} into a ranked list of candidates.

    Highest score first. Anything with category "avoid" sinks to the bottom.
    """
    candidates: list[EmailCandidate] = []
    site_domain = domain_of(website)
    mx_cache: dict[str, bool | None] = {}

    for address, source in raw_emails.items():
        address = address.strip().lower()
        if not looks_like_email(address):
            continue

        score, category, reason = _classify(address)
        email_domain = domain_of(address)
        on_domain = bool(site_domain) and same_domain(address, website)

        if on_domain:
            score += 25
            reason += "; on the company's own domain"
        elif email_domain in _FREE_PROVIDERS:
            score -= 5
            reason += "; free mailbox provider"
        elif site_domain and email_domain != site_domain:
            score -= 20
            reason += f"; different domain ({email_domain}) - verify this belongs to the company"

        mx_ok: bool | None = None
        if check_mx:
            if email_domain not in mx_cache:
                mx_cache[email_domain] = mx_records_exist(email_domain)
            mx_ok = mx_cache[email_domain]
            if mx_ok is False:
                score -= 200
                reason += "; NO mail server found for this domain"

        candidates.append(
            EmailCandidate(
                address=address,
                source_url=source,
                score=score,
                category=category,
                reason=reason,
                valid_syntax=True,
                domain_matches_website=on_domain,
                mx_ok=mx_ok,
            )
        )

    candidates.sort(key=lambda c: (-c.score, c.address))
    return candidates


def select_recipients(candidates: list[EmailCandidate]) -> tuple[list[str], list[str], str, bool]:
    """
    Decide who to write to.

    Returns (to, cc, explanation, needs_review).

    A second address only goes on CC when it is a *different department* that
    is also clearly relevant - never two general inboxes, never a guess.
    """
    usable = [c for c in candidates if c.mx_ok is not False and c.score > -20]
    if not usable:
        # Nothing safe to write to. If the only addresses are departments we
        # avoid (HR, support, press), name them so you can decide - we never
        # pick one automatically.
        rejected = [c for c in candidates if c.mx_ok is not False]
        if rejected:
            listed = ", ".join(f"{c.address} ({c.reason.split(';')[0]})" for c in rejected[:4])
            return [], [], (
                "Only addresses we would normally avoid were found: "
                f"{listed}. Flagged for your review rather than guessing."
            ), True
        dead = [c.address for c in candidates if c.mx_ok is False]
        if dead:
            return [], [], (
                "Addresses were found but their domain has no mail server: "
                f"{', '.join(dead[:3])}."
            ), True
        return [], [], "No usable email address found.", True

    best = usable[0]
    to = [best.address]
    cc: list[str] = []
    needs_review = False
    notes = [f"Primary: {best.address} ({best.category}, score {best.score}, {best.reason})."]

    if best.score < 40:
        needs_review = True
        notes.append("Best available address is weak - please confirm before sending.")
    if best.category == "avoid":
        needs_review = True
        notes.append("Only a department we would normally avoid was found.")
    if not best.domain_matches_website and best.score < 70:
        needs_review = True
        notes.append("Address is not on the company's own domain.")

    # A near-tie between two genuinely different relevant departments -> CC.
    strong_categories = {"green coffee", "purchasing", "sourcing", "trading", "management"}
    for other in usable[1:]:
        if len(cc) >= 1:
            break
        if other.address == best.address:
            continue
        if (
            other.score >= 60
            and other.category != best.category
            and (other.category in strong_categories or best.category in strong_categories)
            and other.domain_matches_website
        ):
            cc.append(other.address)
            notes.append(f"CC: {other.address} ({other.category}) - a different relevant desk.")

    # Two similarly-strong candidates in the SAME category is ambiguous -> ask.
    if len(usable) > 1 and usable[1].score >= best.score - 5 and usable[1].category == best.category:
        needs_review = True
        notes.append(
            f"Ambiguous: {best.address} and {usable[1].address} score almost the same "
            "and belong to the same kind of department."
        )

    return to, cc, " ".join(notes), needs_review


def notes_for_tracker(candidates: list[EmailCandidate], limit: int = 4) -> str:
    """Short 'Notes / memory' line listing every relevant address we found."""
    relevant = [c for c in candidates if c.category != "avoid" and c.mx_ok is not False][:limit]
    if not relevant:
        return "No usable email address found on the website."
    parts = [f"{c.address} ({c.category})" for c in relevant]
    if len(relevant) == 1:
        return f"Email found: {parts[0]}."
    return f"{len(relevant)} relevant emails identified: " + ", ".join(parts) + "."
