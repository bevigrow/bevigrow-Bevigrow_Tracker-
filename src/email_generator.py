"""
Building the actual message.

Your approved template in config/email_template.md is the source of truth.
This module never rewrites it - it only substitutes {{placeholders}}.

Personalisation is limited, by design, to:
  * the salutation
  * one optional context sentence that must be supported by the research

If Claude is unavailable, both fall back to safe, factual defaults.
"""

from __future__ import annotations

import re
from pathlib import Path

from src.config import CONFIG_DIR, settings
from src.logging_setup import get_logger
from src.models import Channel, PreparedMessage, PersonCandidate, ResearchResult
from src.utils import read_text

log = get_logger("email_generator")

TEMPLATE_EMAIL = CONFIG_DIR / "email_template.md"
TEMPLATE_FOLLOWUP = CONFIG_DIR / "followup_template.md"
TEMPLATE_WEBSITE = CONFIG_DIR / "website_enquiry_template.md"
TEMPLATE_LINKEDIN = CONFIG_DIR / "linkedin_templates.md"

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


class TemplateError(RuntimeError):
    pass


def load_template(path: Path) -> tuple[str, str]:
    """Return (subject, body) from a template file, comments stripped."""
    raw = read_text(path)
    if not raw.strip():
        raise TemplateError(f"Template file is missing or empty: {path}")

    lines = [ln for ln in raw.splitlines() if not ln.lstrip().startswith("#")]
    cleaned = "\n".join(lines)

    match = re.search(r"^\s*SUBJECT:\s*(.+?)\s*$", cleaned, re.M)
    if not match:
        raise TemplateError(f"Template {path.name} has no 'SUBJECT:' line.")
    subject = match.group(1).strip()

    _, sep, body = cleaned.partition("\n---")
    if not sep:
        raise TemplateError(f"Template {path.name} has no '---' separator after the subject.")

    return subject, body.strip("\n")


def _sender_values() -> dict[str, str]:
    return {
        "sender_name": settings.sender_name or "[SENDER_NAME not set in .env]",
        "sender_title": settings.sender_title,
        "sender_company": settings.sender_company or "BeviGrow",
        "sender_phone": settings.sender_phone,
        "sender_email": settings.gmail_sender,
        "sender_website": settings.sender_website,
        "sender_location": settings.sender_location,
        "sender_linkedin": settings.sender_linkedin,
    }


def render(template_text: str, values: dict[str, str]) -> str:
    """Substitute {{placeholders}}; unknown ones become empty and are reported."""
    missing: list[str] = []

    def sub(match: re.Match) -> str:
        key = match.group(1)
        if key not in values:
            missing.append(key)
            return ""
        return values[key] or ""

    out = _PLACEHOLDER_RE.sub(sub, template_text)
    if missing:
        log.warning("Template used unknown placeholders: %s", ", ".join(sorted(set(missing))))

    # Tidy up the gaps left by empty placeholders, e.g. an empty first name
    # turning "Hello {{contact_first_name}}," into "Hello ,".
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s+([,.;:!?])", r"\1", out)
    out = re.sub(r"^([A-Za-z]+),$", r"\1,", out, flags=re.M)
    out = re.sub(r" +\n", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip() + "\n"


def _drop_empty_signature_lines(body: str) -> str:
    """A blank phone/website line in the signature looks sloppy - remove it."""
    lines = body.splitlines()
    out: list[str] = []
    for line in lines:
        if line.strip() == "" and out and out[-1].strip() == "":
            continue
        out.append(line)
    return "\n".join(out)


def build_personalisation(result: ResearchResult, person: PersonCandidate | None,
                          use_llm: bool = True) -> dict[str, str]:
    """Decide the salutation and context sentence."""
    from src import contact_research, llm as llm_mod

    notes: list[str] = []
    salutation = ""
    context = ""

    if use_llm and llm_mod.available():
        try:
            data = llm_mod.personalise(
                company=result.resolved_company_name,
                person_name=person.name if person else "",
                person_title=person.title if person else "",
                country=result.country,
                description=result.description,
                research_brief=result.research_brief,
                priority=result.relevance.priority.value,
            )
            salutation = (data.get("salutation") or "").strip()
            context = (data.get("context_sentence") or "").strip()
            notes.extend(n for n in (data.get("notes") or []) if isinstance(n, str))
        except Exception as exc:
            log.warning("Personalisation via Claude failed, using safe default: %s", exc)
            notes.append(f"Claude personalisation failed ({exc}); used a neutral salutation.")

    if not salutation:
        if person and person.name:
            salutation = f"Dear {person.name},"
            notes.append("Salutation uses the verified contact's full name.")
        else:
            salutation = contact_research.fallback_salutation(result.resolved_company_name)
            notes.append("No contact person verified - addressed the company.")

    # A safety net: the salutation must never contain a name we did not verify.
    if person is None and re.search(r"(?i)\bdear (mr|ms|mrs|herr|frau)\b", salutation):
        salutation = contact_research.fallback_salutation(result.resolved_company_name)
        notes.append("Rejected a personal salutation because no person was verified.")

    if context:
        notes.append("Context sentence added from research.")

    return {"salutation": salutation, "context_sentence": context, "_notes": notes}


def _values_for(result: ResearchResult, person: PersonCandidate | None,
                personalisation: dict[str, str], extra: dict[str, str] | None = None) -> dict[str, str]:
    values = _sender_values()
    values.update(
        {
            "salutation": personalisation["salutation"],
            "context_sentence": personalisation["context_sentence"],
            "company_name": result.resolved_company_name,
            "contact_first_name": person.first_name if person else "",
            "contact_full_name": person.name if person else "",
            "contact_title": person.title if person else "",
            "country": result.country,
            "website": result.website,
        }
    )
    if extra:
        values.update(extra)
    return values


def build_email(result: ResearchResult, person: PersonCandidate | None,
                to: list[str], cc: list[str], use_llm: bool = True) -> PreparedMessage:
    """The main outreach email, ready for your approval."""
    subject_tpl, body_tpl = load_template(TEMPLATE_EMAIL)
    personalisation = build_personalisation(result, person, use_llm=use_llm)
    values = _values_for(result, person, personalisation)

    subject = render(subject_tpl, values).strip()
    body = _drop_empty_signature_lines(render(body_tpl, values))

    bcc = [settings.outreach_bcc] if settings.outreach_bcc else []

    return PreparedMessage(
        channel=Channel.EMAIL,
        to=to,
        cc=cc,
        bcc=bcc,
        subject=subject,
        body=body,
        target_url=to[0] if to else "",
        salutation_used=personalisation["salutation"],
        personalisation_notes=personalisation.get("_notes", []),
    )


def build_followup(result: ResearchResult, person: PersonCandidate | None,
                   to: list[str], original_subject: str, date_contacted: str,
                   use_llm: bool = False) -> PreparedMessage:
    subject_tpl, body_tpl = load_template(TEMPLATE_FOLLOWUP)
    personalisation = build_personalisation(result, person, use_llm=use_llm)
    values = _values_for(
        result, person, personalisation,
        extra={"original_subject": original_subject, "date_contacted": date_contacted},
    )
    return PreparedMessage(
        channel=Channel.EMAIL,
        to=to,
        subject=render(subject_tpl, values).strip(),
        body=_drop_empty_signature_lines(render(body_tpl, values)),
        target_url=to[0] if to else "",
        salutation_used=personalisation["salutation"],
        personalisation_notes=personalisation.get("_notes", []),
    )


def build_website_enquiry(result: ResearchResult, person: PersonCandidate | None,
                          form_url: str, use_llm: bool = True) -> PreparedMessage:
    subject_tpl, body_tpl = load_template(TEMPLATE_WEBSITE)
    personalisation = build_personalisation(result, person, use_llm=use_llm)
    values = _values_for(result, person, personalisation)
    return PreparedMessage(
        channel=Channel.WEBSITE_FORM,
        subject=render(subject_tpl, values).strip(),
        body=_drop_empty_signature_lines(render(body_tpl, values)),
        target_url=form_url,
        salutation_used=personalisation["salutation"],
        personalisation_notes=personalisation.get("_notes", []),
    )


def build_linkedin(result: ResearchResult, person: PersonCandidate | None,
                   profile_url: str, use_llm: bool = True) -> PreparedMessage:
    subject_tpl, body_tpl = load_template(TEMPLATE_LINKEDIN)
    personalisation = build_personalisation(result, person, use_llm=use_llm)
    values = _values_for(result, person, personalisation)
    body = render(body_tpl, values)

    notes = list(personalisation.get("_notes", []))
    note_match = re.search(r"\[CONNECTION NOTE.*?\]\n(.*?)(?:\n\[|\Z)", body, re.S)
    if note_match and len(note_match.group(1).strip()) > 300:
        notes.append(
            f"WARNING: the connection note is {len(note_match.group(1).strip())} characters - "
            "LinkedIn allows 300. Shorten it before sending."
        )

    return PreparedMessage(
        channel=Channel.LINKEDIN,
        subject=render(subject_tpl, values).strip(),
        body=body,
        target_url=profile_url,
        salutation_used=personalisation["salutation"],
        personalisation_notes=notes,
    )


def check_templates() -> list[str]:
    """Validate every template at startup so problems surface before a run."""
    problems: list[str] = []
    for path in (TEMPLATE_EMAIL, TEMPLATE_FOLLOWUP, TEMPLATE_WEBSITE, TEMPLATE_LINKEDIN):
        try:
            subject, body = load_template(path)
            if not body.strip():
                problems.append(f"{path.name}: body is empty")
            unknown = set(_PLACEHOLDER_RE.findall(subject + body)) - {
                "salutation", "context_sentence", "company_name", "contact_first_name",
                "contact_full_name", "contact_title", "country", "website",
                "sender_name", "sender_title", "sender_company", "sender_phone",
                "sender_email", "sender_website", "sender_location", "sender_linkedin",
                "original_subject", "date_contacted",
            }
            if unknown:
                problems.append(f"{path.name}: unknown placeholders {sorted(unknown)}")
        except TemplateError as exc:
            problems.append(str(exc))
    return problems
