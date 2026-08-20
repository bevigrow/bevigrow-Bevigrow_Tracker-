"""
The data shapes that flow through the pipeline.

Plain dataclasses, all JSON-serialisable, so every intermediate result can be
written to data/results/ and inspected later without a database.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from enum import Enum
from typing import Any


# --------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------
class Outcome(str, Enum):
    """Final per-company result. Mirrors section 21 of the build spec."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    ALREADY_CONTACTED = "ALREADY_CONTACTED"
    NO_EMAIL = "NO_EMAIL"
    FORM_REQUIRED = "FORM_REQUIRED"
    LINKEDIN_MANUAL = "LINKEDIN_MANUAL"
    SKIPPED = "SKIPPED"
    IRRELEVANT = "IRRELEVANT"
    SIMULATED = "SIMULATED"  # TEST_MODE: everything worked, nothing was sent


class Priority(str, Enum):
    HIGH = "HIGH PRIORITY"
    MEDIUM = "MEDIUM PRIORITY"
    LOW = "LOW PRIORITY"
    IRRELEVANT = "IRRELEVANT"
    UNCERTAIN = "UNCERTAIN"


class Channel(str, Enum):
    """Values accepted by the BeviGrow tracker API (`ContactMethod`)."""

    EMAIL = "email"
    LINKEDIN = "linkedin"
    WEBSITE_FORM = "website_form"
    INSTAGRAM = "instagram"
    PHONE = "phone"
    WHATSAPP = "whatsapp"
    OTHER = "other"


class TrackerStatus(str, Enum):
    """Values accepted by the BeviGrow tracker API (`OutreachStatus`)."""

    FOLLOW_UP_NEEDED = "follow_up_needed"
    FOLLOW_UP_SENT = "follow_up_sent"
    WAITING_REPLY = "waiting_reply"
    REPLIED = "replied"
    NO_RESPONSE = "no_response"
    NOT_INTERESTED = "not_interested"


# --------------------------------------------------------------------------
# Building blocks
# --------------------------------------------------------------------------
@dataclass
class Evidence:
    """Every fact we keep must be traceable to where we found it."""

    value: str
    source_url: str
    how: str = ""  # e.g. "mailto link on /contact", "web search result"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EmailCandidate:
    address: str
    source_url: str = ""
    score: int = 0
    category: str = "unknown"  # purchasing / sourcing / sales / general / avoid ...
    reason: str = ""
    valid_syntax: bool = True
    domain_matches_website: bool = False
    mx_ok: bool | None = None  # None = not checked

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PersonCandidate:
    name: str
    title: str = ""
    email: str = ""
    linkedin_url: str = ""
    source_url: str = ""
    score: int = 0
    reason: str = ""

    @property
    def first_name(self) -> str:
        return self.name.split()[0] if self.name else ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CompanyInput:
    """One row of the input file."""

    company: str
    city: str = ""
    country: str = ""
    website: str = ""
    notes: str = ""
    row_number: int = 0

    @property
    def location(self) -> str:
        return ", ".join(p for p in (self.city, self.country) if p)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Relevance:
    priority: Priority = Priority.UNCERTAIN
    reason: str = ""
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["priority"] = self.priority.value
        return d


@dataclass
class ResearchResult:
    """Everything we learned about one company."""

    company_input: CompanyInput
    resolved_company_name: str = ""
    website: str = ""
    website_source: str = ""
    country: str = ""
    city: str = ""
    description: str = ""

    emails: list[EmailCandidate] = field(default_factory=list)
    people: list[PersonCandidate] = field(default_factory=list)

    linkedin_company_url: str = ""
    linkedin_person_url: str = ""
    linkedin_profiles: list[str] = field(default_factory=list)
    contact_page_url: str = ""
    contact_form_url: str = ""
    phone: str = ""

    relevance: Relevance = field(default_factory=Relevance)
    evidence: list[Evidence] = field(default_factory=list)
    research_brief: str = ""  # free-text notes from the research step
    warnings: list[str] = field(default_factory=list)
    pages_crawled: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    @property
    def primary_email(self) -> EmailCandidate | None:
        usable = [e for e in self.emails if e.valid_syntax and e.category != "avoid"]
        return usable[0] if usable else None

    @property
    def primary_person(self) -> PersonCandidate | None:
        return self.people[0] if self.people else None

    def add_evidence(self, value: str, source_url: str, how: str = "") -> None:
        self.evidence.append(Evidence(value=value, source_url=source_url, how=how))

    def to_dict(self) -> dict[str, Any]:
        return {
            "company_input": self.company_input.to_dict(),
            "resolved_company_name": self.resolved_company_name,
            "website": self.website,
            "website_source": self.website_source,
            "country": self.country,
            "city": self.city,
            "description": self.description,
            "emails": [e.to_dict() for e in self.emails],
            "people": [p.to_dict() for p in self.people],
            "linkedin_company_url": self.linkedin_company_url,
            "linkedin_person_url": self.linkedin_person_url,
            "linkedin_profiles": self.linkedin_profiles,
            "contact_page_url": self.contact_page_url,
            "contact_form_url": self.contact_form_url,
            "phone": self.phone,
            "relevance": self.relevance.to_dict(),
            "evidence": [e.to_dict() for e in self.evidence],
            "research_brief": self.research_brief,
            "warnings": self.warnings,
            "pages_crawled": self.pages_crawled,
        }


@dataclass
class PreparedMessage:
    """A message that is ready for your approval. Nothing is sent before this."""

    channel: Channel
    to: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    subject: str = ""
    body: str = ""
    target_url: str = ""  # LinkedIn URL or contact-form URL
    salutation_used: str = ""
    personalisation_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["channel"] = self.channel.value
        return d


@dataclass
class CompanyResult:
    """The full record of what happened for one company."""

    company: str
    outcome: Outcome = Outcome.FAILED
    reason: str = ""
    research: ResearchResult | None = None
    message: PreparedMessage | None = None
    sent_at: str = ""
    tracker_record_id: int | None = None
    next_follow_up: str = ""
    error: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "company": self.company,
            "outcome": self.outcome.value,
            "reason": self.reason,
            "research": self.research.to_dict() if self.research else None,
            "message": self.message.to_dict() if self.message else None,
            "sent_at": self.sent_at,
            "tracker_record_id": self.tracker_record_id,
            "next_follow_up": self.next_follow_up,
            "error": self.error,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False, default=str)


def iso_today() -> str:
    return date.today().isoformat()
