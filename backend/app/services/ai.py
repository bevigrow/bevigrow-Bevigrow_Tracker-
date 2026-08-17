"""Summaries, dashboard insights and follow-up ranking.

The actual model call lives in `providers.py`, which supports Google Gemini
(free tier) and Anthropic Claude Haiku. This module only shapes the prompts and
parses the results.

Every function degrades gracefully: with no provider configured, or when one
errors, a deterministic local fallback is returned so the product keeps working
and nothing 500s because an AI was unavailable.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re

from ..config import settings
from . import providers

log = logging.getLogger("bevigrow.ai")


def ai_enabled() -> bool:
    return providers.active_provider() is not None


def active_model() -> str:
    return providers.active_model()


BRAND_SYSTEM = (
    "You are the operations assistant for BeviGrow, an international coffee "
    "export and import trading company. You write for a professional B2B "
    "audience: precise, factual, no filler, no emoji, no marketing language. "
    "Only discuss coffee trading topics present in the input — never invent "
    "quantities, prices, dates or commitments that were not stated."
)


def _complete(prompt: str, *, system: str = BRAND_SYSTEM, max_tokens: int | None = None) -> str | None:
    """One model call. Returns None when AI is unavailable or errored."""
    return providers.complete(prompt, system, max_tokens or settings.AI_MAX_TOKENS)


# ------------------------------------------------------------- meeting summary


def summarize_interaction(
    notes: str, company_name: str | None = None, country: str | None = None
) -> tuple[str, bool]:
    """Turn raw shorthand notes into a professional interaction summary.

    Returns (summary, used_ai).
    """
    who = company_name or "the counterparty"
    where = f", {country}" if country else ""
    prompt = (
        "Rewrite the raw notes below into a short professional summary of a "
        "coffee B2B interaction.\n\n"
        "Rules:\n"
        "- 2 to 4 sentences, single paragraph, third person, past tense.\n"
        "- Keep every concrete detail: product, quantity, roast/bean type, "
        "prices, dates, incoterms.\n"
        "- End with the pending next step if one is implied.\n"
        "- Output only the summary text, with no heading or preamble.\n\n"
        f"Counterparty: {who}{where}\n"
        f"Raw notes: {notes.strip()}"
    )
    result = _complete(prompt, max_tokens=400)
    if result:
        return result, True
    return _fallback_summary(notes, company_name, country), False


def _fallback_summary(notes: str, company_name: str | None, country: str | None) -> str:
    cleaned = " ".join(notes.split())
    if not cleaned.endswith("."):
        cleaned += "."
    who = company_name or "the counterparty"
    where = f" ({country})" if country else ""
    return f"Interaction logged with {who}{where}. {cleaned} Follow-up pending."


# ---------------------------------------------------------- dashboard insights


# Capped at two lines, and told to skip anything sitting at zero.
#
# The previous version asked for "3 to 5 bullets" covering four fixed topics,
# so it filled the template whichever way the numbers went: on an empty desk it
# produced four sentences whose entire content was that everything was zero.
# The reader can already see the desk is empty. Saying it four times in
# business language is worse than silence, because it buries the one line that
# might have mattered.
#
# Kept at module level so `prompt_fingerprint()` can hash it — see below.
_DASHBOARD_RULES = (
    "Here is today's snapshot of a coffee trading desk as JSON. "
    "Write the briefing a colleague would actually say out loud.\n\n"
    "Rules:\n"
    "- At most 2 bullets, each starting with '- '. Fewer is better.\n"
    "- One short sentence per bullet. Plain words.\n"
    "- Only mention something if it needs a decision or an action. Never "
    "state that a number is zero, and never list several zeros.\n"
    "- If nothing needs attention, reply with exactly one bullet saying "
    "so in a few words.\n"
    "- Use real figures from the data; never invent any.\n"
    "- Avoid the words pipeline, momentum, leverage, robust, operational "
    "and synergy.\n"
    "- Output only the bullets.\n\n"
)


def prompt_fingerprint() -> str:
    """Short hash of the instruction text, used as part of the cache key.

    Insights are cached for half an hour so a page refresh does not re-bill the
    API. That cache was keyed on the kind alone, so editing a prompt changed
    nothing a reader could see until the old entry aged out — the app kept
    serving text written to instructions that no longer existed.

    Hashing only the rules, never the data, means a reworded prompt is a
    different key and supersedes its own cache immediately, while identical
    instructions over changing figures still hit it.
    """
    return hashlib.sha1(_DASHBOARD_RULES.encode()).hexdigest()[:8]


def dashboard_insight(stats: dict) -> tuple[str, bool]:
    """A short narrative readout of today's numbers for the dashboard."""
    prompt = _DASHBOARD_RULES + f"Data: {json.dumps(stats, default=str)}"
    result = _complete(prompt, max_tokens=220)
    if result:
        return result, True
    return _fallback_dashboard(stats), False


def _fallback_dashboard(stats: dict) -> str:
    k = stats.get("kpis", {})
    top = stats.get("top_countries") or []
    # Records, not quotes: a country can be entirely cold outreach, and
    # printing its quote count would report every one of them as "(0)".
    top_txt = (
        ", ".join(f"{c['country']} ({c['count'] + c.get('prospects', 0)})" for c in top[:3])
        or "no markets yet"
    )
    # Same rule as the prompt: only say what is worth acting on. A line
    # reporting a count of zero is one the reader must read before discarding.
    lines: list[str] = []
    if k.get("pending_follow_ups"):
        lines.append(f"- {k['pending_follow_ups']} follow-ups are due — clear these first.")
    if k.get("new_leads"):
        lines.append(f"- {k['new_leads']} new leads still waiting on a first reply.")
    if not lines and k.get("activities_today"):
        lines.append(f"- {k['activities_today']} interactions logged today.")
    if not lines and top:
        lines.append(f"- Busiest market: {top_txt}.")
    if not lines:
        lines.append("- Nothing needs attention today.")
    return "\n".join(lines[:2])


def weekly_highlights(stats: dict) -> tuple[str, bool]:
    prompt = (
        "Below is BeviGrow's coffee trading performance for the last 7 days as "
        "JSON. Write a weekly performance highlight for management.\n\n"
        "Rules:\n"
        "- 4 to 6 bullet points, each starting with '- '.\n"
        "- Compare against the prior period where the data allows.\n"
        "- Call out conversion rate, country momentum, and stalled deals.\n"
        "- Reference real numbers only. Output only the bullets.\n\n"
        f"Data: {json.dumps(stats, default=str)}"
    )
    result = _complete(prompt, max_tokens=600)
    if result:
        return result, True
    return _fallback_dashboard(stats), False


# ------------------------------------------------------- follow-up suggestions


def followup_suggestions(candidates: list[dict]) -> tuple[list[dict], bool]:
    """Rank and explain which accounts need attention.

    `candidates` are pre-filtered dicts with id/company/country/status/
    days_since_contact/activity_count. Returns (suggestions, used_ai).
    """
    if not candidates:
        return [], ai_enabled()

    prompt = (
        "You are triaging a coffee export/import pipeline. For each account "
        "below, decide how urgently BeviGrow should follow up.\n\n"
        "Return ONLY a JSON array (no markdown fence, no commentary). Each "
        "element must be an object with exactly these keys:\n"
        '  "contact_id" (integer, copy from input),\n'
        '  "priority" (one of "high", "medium", "low"),\n'
        '  "reason" (one sentence explaining why, citing days or status),\n'
        '  "suggested_action" (one imperative sentence, max 18 words).\n\n'
        "Rank high priority for: quotations or samples sent with no reply, "
        "accounts silent 5+ days, and accounts with repeated interactions "
        "showing buying intent. Include every account from the input.\n\n"
        f"Accounts: {json.dumps(candidates, default=str)}"
    )
    raw = _complete(prompt, max_tokens=1400)
    parsed = _parse_json_array(raw) if raw else None

    if parsed:
        by_id = {c["contact_id"]: c for c in candidates}
        out: list[dict] = []
        for item in parsed:
            cid = item.get("contact_id")
            base = by_id.get(cid)
            if not base:
                continue
            priority = str(item.get("priority", "medium")).lower()
            out.append(
                {
                    **base,
                    "priority": priority if priority in {"high", "medium", "low"} else "medium",
                    "reason": str(item.get("reason", "")).strip() or _rule_reason(base),
                    "suggested_action": str(item.get("suggested_action", "")).strip()
                    or _rule_action(base),
                }
            )
        if out:
            order = {"high": 0, "medium": 1, "low": 2}
            out.sort(key=lambda s: (order.get(s["priority"], 1), -(s.get("days_since_contact") or 0)))
            return out, True

    return _fallback_suggestions(candidates), False


def _parse_json_array(raw: str) -> list[dict] | None:
    text = raw.strip()
    # Tolerate a stray markdown fence even though the prompt forbids it.
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) else None


def _rule_reason(c: dict) -> str:
    days = c.get("days_since_contact")
    status = str(c.get("status", "")).replace("_", " ")
    if days is None:
        return f"No interaction has ever been logged for this {status} account."
    if days >= 5:
        return f"{c['company_name']} has not been contacted for {days} days."
    return f"Account is at '{status}' and is awaiting a response."


def _rule_action(c: dict) -> str:
    status = str(c.get("status", ""))
    if status == "quotation_sent":
        return "Call to confirm the quotation was received and answer pricing questions."
    if status == "sample_sent":
        return "Ask for sample cupping feedback and propose a trial order volume."
    if status == "negotiation":
        return "Send revised terms in writing and set a decision deadline."
    if status == "new_lead":
        return "Send the company profile and current coffee origin list."
    return "Send a short check-in message and propose a specific next step."


def _fallback_suggestions(candidates: list[dict]) -> list[dict]:
    out = []
    for c in candidates:
        days = c.get("days_since_contact")
        status = str(c.get("status", ""))
        if status in {"quotation_sent", "sample_sent"} or (days is not None and days >= 7):
            priority = "high"
        elif days is None or days >= 4:
            priority = "medium"
        else:
            priority = "low"
        out.append(
            {**c, "priority": priority, "reason": _rule_reason(c), "suggested_action": _rule_action(c)}
        )
    order = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda s: (order[s["priority"]], -(s.get("days_since_contact") or 0)))
    return out
