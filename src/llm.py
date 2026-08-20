"""
The reasoning layer: Claude.

Used for three jobs, and nothing else:

  1. research_company()  - search the public web and write a sourced brief
  2. extract_facts()     - turn that brief + the crawled pages into strict JSON
  3. personalise()       - write the salutation and (optionally) ONE context
                           sentence for your approved template

Everything is optional. Without ANTHROPIC_API_KEY the pipeline still runs -
it falls back to keyword rules and a generic salutation - but the quality of
relevance scoring and personalisation drops a lot.

Hard rule enforced in every prompt: never invent a fact. If it was not seen
in a source, the field comes back empty.
"""

from __future__ import annotations

import json
from typing import Any

from src.config import settings
from src.logging_setup import get_logger

log = get_logger("llm")

_client: Any = None
_unavailable_reason = ""


def available() -> bool:
    return bool(settings.llm_available) and get_client() is not None


def get_client():
    """Lazily build the Anthropic client. Returns None if unusable."""
    global _client, _unavailable_reason
    if _client is not None:
        return _client
    if not settings.llm_available:
        _unavailable_reason = "ANTHROPIC_API_KEY not set (or LLM_ENABLED=false)"
        return None
    try:
        import anthropic

        _client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key,
            timeout=300.0,
            max_retries=3,
        )
        return _client
    except ImportError:
        _unavailable_reason = "the 'anthropic' package is not installed"
    except Exception as exc:
        _unavailable_reason = str(exc)[:200]
    return None


def unavailable_reason() -> str:
    if _unavailable_reason:
        return _unavailable_reason
    if not settings.anthropic_api_key:
        return "ANTHROPIC_API_KEY is not set in .env"
    if not settings.llm_enabled:
        return "LLM_ENABLED is false in .env"
    return "unknown"


# --------------------------------------------------------------------------
# Low-level call helpers
# --------------------------------------------------------------------------
def _text_of(response) -> str:
    return "\n".join(b.text for b in response.content if getattr(b, "type", "") == "text").strip()


def _call(
    *,
    system: str,
    user: str,
    model: str | None = None,
    max_tokens: int = 8000,
    tools: list[dict] | None = None,
    schema: dict | None = None,
    effort: str = "medium",
):
    """One Claude request, with pause_turn resumption for server-side tools."""
    client = get_client()
    if client is None:
        raise RuntimeError(f"Claude unavailable: {unavailable_reason()}")

    output_config: dict[str, Any] = {"effort": effort}
    if schema is not None:
        output_config["format"] = {"type": "json_schema", "schema": schema}

    kwargs: dict[str, Any] = {
        "model": model or settings.anthropic_model,
        "max_tokens": max_tokens,
        "system": system,
        "output_config": output_config,
    }
    if tools:
        kwargs["tools"] = tools

    messages: list[dict[str, Any]] = [{"role": "user", "content": user}]

    for _ in range(6):  # resume loop for pause_turn
        response = client.messages.create(messages=messages, **kwargs)
        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue
        if response.stop_reason == "refusal":
            detail = getattr(response, "stop_details", None)
            raise RuntimeError(
                f"Claude declined this request ({getattr(detail, 'category', 'unknown')})."
            )
        return response

    raise RuntimeError("Claude kept pausing - research did not finish.")


def _json_call(*, system: str, user: str, schema: dict, model: str | None = None,
               max_tokens: int = 8000, effort: str = "medium") -> dict:
    response = _call(
        system=system, user=user, schema=schema, model=model,
        max_tokens=max_tokens, effort=effort,
    )
    raw = _text_of(response)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # output_config guarantees valid JSON, but never crash a whole run on it.
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise RuntimeError("Claude returned something that was not JSON.")


# --------------------------------------------------------------------------
# 1. Research
# --------------------------------------------------------------------------
_RESEARCH_SYSTEM = """You are a B2B research analyst for BeviGrow, a coffee grower and \
exporter in Yercaud, Tamil Nadu, India. BeviGrow sells Indian green coffee: RC Robusta \
(Grades AA, A, B and PB) and Arabica Highland Washed green beans.

Your job is to research ONE company and report only what you can actually verify from \
public sources.

ABSOLUTE RULES
- Never invent a website, an email address, a person's name or a job title.
- Every concrete contact detail you report must be followed by the URL you saw it on.
- If you cannot verify something, write "not found" instead of guessing.
- Do not report an email address you merely think is likely (e.g. do not construct \
firstname.lastname@domain). Only report addresses you actually saw published.
- Prefer the company's own website over directories, aggregators or data brokers.

Report, in plain prose with a source URL beside each item:
1. Official website
2. Country and city
3. What the company actually does (roaster / importer / trader / wholesaler / retailer / other)
4. Whether they buy or import GREEN (unroasted) coffee, and any evidence of Robusta or \
Indian origin interest
5. Rough size and whether they look like a realistic B2B green-coffee buyer
6. Named people relevant to buying coffee (owner, founder, MD, green coffee buyer, \
purchasing/sourcing/import manager) with their job titles
7. Published email addresses and which department each belongs to
8. LinkedIn company page URL, and a LinkedIn profile URL for a relevant person if published
9. The URL of their contact or enquiry page
10. Anything that would make outreach a bad idea (e.g. they are a competitor exporter, \
they are closed, they only sell roasted retail)

Keep it under 500 words."""


def research_company(company: str, city: str = "", country: str = "",
                     website_hint: str = "") -> str:
    """Return a sourced research brief as free text. Raises on hard failure."""
    place = ", ".join(p for p in (city, country) if p)
    hint = f"\nTheir website may be: {website_hint}" if website_hint else ""
    user = (
        f"Research this company for BeviGrow green coffee outreach.\n\n"
        f"Company: {company}\n"
        f"Location: {place or 'unknown'}{hint}\n\n"
        f"Search the web and report what you can verify."
    )

    response = _call(
        system=_RESEARCH_SYSTEM,
        user=user,
        tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 8}],
        max_tokens=8000,
        effort="medium",
    )
    brief = _text_of(response)
    log.debug("Research brief for %s: %d chars", company, len(brief))
    return brief


# --------------------------------------------------------------------------
# 2. Structured extraction
# --------------------------------------------------------------------------
_FACTS_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "official_website": {"type": "string", "description": "Homepage URL, or '' if unverified"},
        "country": {"type": "string"},
        "city": {"type": "string"},
        "description": {"type": "string", "description": "One or two factual sentences"},
        "business_type": {
            "type": "string",
            "enum": ["roaster", "importer", "trader", "wholesaler", "retailer",
                     "cafe", "producer_exporter", "other", "unknown"],
        },
        "buys_green_coffee": {"type": "string", "enum": ["yes", "likely", "no", "unknown"]},
        "priority": {
            "type": "string",
            "enum": ["HIGH PRIORITY", "MEDIUM PRIORITY", "LOW PRIORITY", "IRRELEVANT", "UNCERTAIN"],
        },
        "priority_reason": {"type": "string"},
        "signals": {"type": "array", "items": {"type": "string"}},
        "contact_people": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "title": {"type": "string"},
                    "email": {"type": "string"},
                    "linkedin_url": {"type": "string"},
                    "source_url": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": ["name", "title", "email", "linkedin_url", "source_url", "confidence"],
                "additionalProperties": False,
            },
        },
        "linkedin_company_url": {"type": "string"},
        "contact_page_url": {"type": "string"},
        "best_email": {"type": "string", "description": "The single best published address, or ''"},
        "best_email_reason": {"type": "string"},
        "uncertain_flags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Anything a human should check before sending",
        },
    },
    "required": [
        "official_website", "country", "city", "description", "business_type",
        "buys_green_coffee", "priority", "priority_reason", "signals",
        "contact_people", "linkedin_company_url", "contact_page_url",
        "best_email", "best_email_reason", "uncertain_flags",
    ],
    "additionalProperties": False,
}

_FACTS_SYSTEM = """You convert research notes into strict JSON for BeviGrow, an Indian \
green coffee exporter (RC Robusta AA/A/B/PB and Arabica Highland Washed).

RULES
- Only fill a field if the information appears in the material you were given.
- Never construct or guess an email address. If no address was published, use "".
- Never invent a person. If no named person was published, return an empty list.
- source_url must be a URL that actually appeared in the material.

PRIORITY GUIDE
- HIGH PRIORITY: imports or buys green coffee directly; a roaster that sources its own \
green; a green coffee trader, importer or wholesaler; explicit Robusta or Indian-origin interest.
- MEDIUM PRIORITY: a roaster or coffee wholesaler that probably buys green but it is not stated; \
a specialty coffee company of reasonable size.
- LOW PRIORITY: very small operation, cafe that buys roasted beans, mainly a retailer.
- IRRELEVANT: not a coffee business at all, or a competing green coffee producer/exporter, \
or clearly closed.
- UNCERTAIN: too little information. Use this rather than rejecting a company for thin data."""


def extract_facts(company: str, city: str, country: str, research_brief: str,
                  website: str, site_text: str, found_emails: dict[str, str],
                  found_linkedin: dict[str, str]) -> dict:
    """Merge the research brief and crawled pages into one strict JSON record."""
    email_lines = "\n".join(f"  {a}  (seen on {u})" for a, u in list(found_emails.items())[:25])
    li_lines = "\n".join(f"  {a}  (seen on {u})" for a, u in list(found_linkedin.items())[:15])

    user = f"""COMPANY FROM MY LIST
Name: {company}
Location given: {', '.join(p for p in (city, country) if p) or 'unknown'}
Website used for crawling: {website or 'none'}

--- RESEARCH BRIEF (from web search) ---
{research_brief or '(no research brief available)'}

--- EMAIL ADDRESSES ACTUALLY PUBLISHED ON THEIR WEBSITE ---
{email_lines or '  (none found)'}

--- LINKEDIN LINKS FOUND ON THEIR WEBSITE ---
{li_lines or '  (none found)'}

--- TEXT OF THEIR WEBSITE PAGES ---
{site_text[:20000] or '(website could not be crawled)'}

Produce the JSON record."""

    return _json_call(
        system=_FACTS_SYSTEM,
        user=user,
        schema=_FACTS_SCHEMA,
        max_tokens=8000,
        effort="medium",
    )


# --------------------------------------------------------------------------
# 3. Personalisation
# --------------------------------------------------------------------------
_PERSONALISE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "salutation": {
            "type": "string",
            "description": "e.g. 'Dear Mr Benecke,' or 'Dear Benecke Coffee team,'",
        },
        "context_sentence": {
            "type": "string",
            "description": "ONE short sentence supported by the research, or '' if nothing is "
                           "solidly verifiable. No flattery, no invented facts, no flavour notes.",
        },
        "subject_suffix": {
            "type": "string",
            "description": "Optional short addition to the subject line, or ''",
        },
        "notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["salutation", "context_sentence", "subject_suffix", "notes"],
    "additionalProperties": False,
}

_PERSONALISE_SYSTEM = """You personalise an already-approved B2B outreach email for \
BeviGrow, an Indian green coffee grower/exporter.

You are NOT rewriting the email. You produce only two small pieces:

1. salutation
   - If a contact person's name AND their role were verified: use their family name with a \
neutral honorific, e.g. "Dear Mr Schmidt," / "Dear Ms Laine,". If you are not certain of the \
person's gender or which part is the family name, use the full name: "Dear Anna Laine,".
   - If no person was verified: address the company, e.g. "Dear Benecke Coffee team,".
   - Never invent a name. Never use "Dear Sir or Madam" unless nothing else is possible.

2. context_sentence
   - ONE short, factual, businesslike sentence referring to something genuinely stated in the \
research (e.g. "I saw that you import green coffee for European roasters.").
   - It must be defensible from the research text. If nothing is solidly verifiable, return "".
   - Never claim to have met them, used their product, or read something you did not.
   - Never mention flavour notes, cup scores or tasting descriptors.
   - Never promise prices, volumes or certifications.

Write in plain professional English. Keep it neutral and short."""


def personalise(company: str, person_name: str, person_title: str, country: str,
                description: str, research_brief: str, priority: str) -> dict:
    user = f"""Company: {company}
Country: {country or 'unknown'}
Verified contact person: {person_name or '(none verified)'}
Their job title: {person_title or '(unknown)'}
What they do: {description or '(unknown)'}
Relevance: {priority}

Research notes:
{(research_brief or '(none)')[:6000]}

Produce the salutation and, only if genuinely supported above, one context sentence."""

    return _json_call(
        system=_PERSONALISE_SYSTEM,
        user=user,
        schema=_PERSONALISE_SCHEMA,
        model=settings.anthropic_fast_model,
        max_tokens=2000,
        effort="low",
    )


# --------------------------------------------------------------------------
# 4. Reply classification (used by the reply-processing command)
# --------------------------------------------------------------------------
_REPLY_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["replied", "not_interested", "follow_up_needed", "no_response", "unclear"],
        },
        "summary": {"type": "string", "description": "One sentence: what they said"},
        "next_action": {"type": "string"},
        "follow_up_in_days": {"type": "integer"},
        "is_auto_reply": {"type": "boolean"},
    },
    "required": ["status", "summary", "next_action", "follow_up_in_days", "is_auto_reply"],
    "additionalProperties": False,
}

_REPLY_SYSTEM = """You read replies to BeviGrow's green coffee outreach and classify them.

- "not_interested" only when they clearly decline or ask not to be contacted.
- "follow_up_needed" when they ask us to come back later, or ask for something we must send.
- "replied" for any other genuine human answer, including questions and requests for samples \
or prices.
- "no_response" is never correct here - there IS a reply.
- Out-of-office and delivery failures: set is_auto_reply true and status "unclear".
Never mark someone not interested just because the reply is short."""


def classify_reply(company: str, our_message: str, their_reply: str) -> dict:
    user = f"""Company: {company}

--- WHAT WE SENT ---
{our_message[:4000]}

--- THEIR REPLY ---
{their_reply[:6000]}

Classify it."""
    return _json_call(
        system=_REPLY_SYSTEM,
        user=user,
        schema=_REPLY_SCHEMA,
        model=settings.anthropic_fast_model,
        max_tokens=1500,
        effort="low",
    )
