"""Filling in one email from the example you wrote.

Substitution, not composition. The template's words are yours and stay yours:
this replaces the placeholders and touches nothing else, which is what makes
the promise in the spec — that the AI may not alter grades, prices,
certifications or origin claims — something the code guarantees rather than
something a model was asked nicely to respect.

A model can still be pointed at the *greeting* later, where "Dear Tanaka San"
versus "Dear ABC Coffee Team" is a judgement call. Everything below the
greeting is copied verbatim, every time.
"""
from __future__ import annotations

import json
import logging
import re

from ..models import Campaign, CampaignTarget
from .geo import tidy

log = logging.getLogger("bevigrow.template")

# Every placeholder style seen in a hand-written template: #NAME, {{name}},
# {name}, [NAME], %NAME%. Captured so the whole token can be replaced.
PLACEHOLDER = re.compile(
    r"#(?P<hash>[A-Z][A-Z0-9_]{2,})"
    r"|\{\{\s*(?P<double>[\w.\- ]+?)\s*\}\}"
    r"|\{\s*(?P<single>[\w.\- ]+?)\s*\}"
    r"|\[(?P<square>[A-Za-z][\w\- ]{2,})\]"
    r"|%(?P<percent>[A-Za-z][\w\-]{2,})%"
)

# Placeholder name (normalised) -> which field answers it.
FIELDS = {
    "company": "company_name",
    "company_name": "company_name",
    "companyname": "company_name",
    "business": "company_name",
    "contact": "contact_person",
    "contact_person": "contact_person",
    "person": "contact_person",
    "name": "contact_person",
    "first_name": "contact_person",
    "country": "country",
    "city": "location",
    "location": "location",
    "website": "website",
    "site": "website",
    "category": "category",
    "type": "category",
    "phone": "phone",
    "email": "email",
}


def _normalise(token: str) -> str:
    return re.sub(r"[\s\-.]+", "_", token.strip().casefold())


# What a category column tends to say, and how it reads inside a sentence.
BUSINESS_AREAS: dict[str, str] = {
    "importer": "coffee importing",
    "import": "coffee importing",
    "exporter": "coffee exporting",
    "roaster": "coffee roasting",
    "roastery": "coffee roasting",
    "micro roaster": "speciality coffee roasting",
    "specialty": "speciality coffee",
    "speciality": "speciality coffee",
    "distributor": "coffee distribution",
    "wholesaler": "wholesale coffee",
    "wholesale": "wholesale coffee",
    "retailer": "coffee retail",
    "cafe": "the café trade",
    "coffee shop": "the café trade",
    "restaurant": "hospitality",
    "hotel": "hospitality",
    "trader": "the coffee trade",
    "supermarket": "grocery retail",
}

GENERIC_AREA = "the coffee trade"


def _business_area(category: str | None) -> str:
    label = tidy(category or "").casefold()
    if not label:
        return GENERIC_AREA
    if label in BUSINESS_AREAS:
        return BUSINESS_AREAS[label]
    # "Specialty Coffee Importer" contains a word we know.
    for needle, phrase in BUSINESS_AREAS.items():
        if needle in label:
            return phrase
    return GENERIC_AREA


def _value_for(token: str, target: CampaignTarget) -> str | None:
    """What this placeholder should become, or None if nothing sensible fits."""
    key = _normalise(token)
    company = tidy(target.company_name) or "your team"

    # The team greeting, which is the one placeholder that composes rather than
    # copies: "#COMPANY_TEAM" wants "ABC Coffee Team", not "ABC Coffee".
    if key in ("company_team", "team", "companyteam"):
        return f"{company} Team"

    # A greeting that prefers a real person and falls back to the team, so a
    # template written for one still works on a row that has no contact name.
    if key in ("greeting", "salutation", "dear"):
        person = tidy(target.contact_person or "")
        return person or f"{company} Team"

    # "Given [Company Name]'s activities in [relevant business area], …"
    #
    # Not a column in any spreadsheet — it is a description of what the company
    # does, and the sentence around it needs a phrase rather than a job title.
    # A file's "Importer" would read as "activities in Importer", so the label
    # is turned into language. Anything unrecognised falls back to a phrase
    # that is true of every company on a coffee buyer list, because holding
    # back the whole campaign over one adjective helps nobody.
    if key in (
        "relevant_business_area",
        "business_area",
        "relevant_area",
        "business_activity",
        "activity",
        "sector",
    ):
        return _business_area(target.category)

    field = FIELDS.get(key)
    if field:
        value = tidy(getattr(target, field, None) or "")
        if value:
            return value
        # A missing contact name is normal and has an obvious stand-in. A
        # missing company name does too. The rest do not, and are handled
        # by the caller as an unfillable placeholder.
        if field == "contact_person":
            return f"{company} Team"
        if field == "company_name":
            return "your team"
        return None

    # Anything else the file happened to carry, by column heading.
    if target.extra:
        try:
            extra = json.loads(target.extra)
        except (ValueError, TypeError):
            extra = {}
        for heading, value in extra.items():
            if _normalise(heading) == key and tidy(str(value)):
                return tidy(str(value))
    return None


def fill(text: str, target: CampaignTarget) -> tuple[str, list[str]]:
    """Substitute placeholders. Returns the text and any it could not fill."""
    unfilled: list[str] = []

    def replace(match: re.Match) -> str:
        token = next(g for g in match.groups() if g is not None)
        value = _value_for(token, target)
        if value is None:
            unfilled.append(token)
            return match.group(0)
        return value

    return PLACEHOLDER.sub(replace, text or ""), unfilled


def render(campaign: Campaign, target: CampaignTarget) -> tuple[str, str]:
    """The subject and body that will actually be sent to this address.

    An unfillable placeholder is left visible on purpose. The engine treats a
    draft that still contains one as not sendable — a real email beginning
    "Dear #COMPANY_TEAM," is the single most embarrassing thing this system
    could do, and it is better to stop and say so.
    """
    template = campaign.template
    if template is None:
        raise ValueError("This campaign has no email template.")

    subject, missing_subject = fill(template.subject or "", target)
    body, missing_body = fill(template.body or "", target)

    missing = missing_subject + missing_body
    if missing:
        log.info(
            "Campaign %s: %s has unfilled placeholders %s",
            campaign.id,
            target.company_name,
            sorted(set(missing)),
        )
    return subject.strip(), body


def unfilled_tokens(campaign: Campaign, target: CampaignTarget) -> list[str]:
    """Placeholders this row cannot answer — the reason a draft is held back."""
    template = campaign.template
    if template is None:
        return []
    _, a = fill(template.subject or "", target)
    _, b = fill(template.body or "", target)
    return sorted(set(a + b))
