"""Talking to the campaign in plain words.

The division of labour here is the whole point, and it is deliberately lopsided:

    the model decides what you *meant*
    the database decides what is *true*

So the model is asked exactly one question — which of a fixed list of actions
is this, and about which campaign — and its answer is checked against that list
before anything happens. Every number in the reply is then read out of the
database by ordinary code. The model never sees a figure it could round, never
holds a total it could carry wrong, and cannot invent a company that was
emailed. Ask "how many went today?" and the answer comes from the same query
the status panel uses; if it is wrong, the panel is wrong too, which is a bug
that can be found rather than a sentence that reads plausibly.

It also works with no model configured at all. The rules below catch the
phrasings anyone actually types, and the model is the fallback for the rest —
not the other way round.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Campaign, CampaignStatus, CampaignTarget, TargetState
from . import campaigns as cm
from . import providers

log = logging.getLogger("bevigrow.assistant")

ACTIONS = (
    "status",
    "start",
    "pause",
    "stop",
    "send",
    "remaining",
    "failed",
    "duplicates",
    "skipped",
    "today",
    "company",
    "help",
)


@dataclass
class Intent:
    action: str
    campaign_id: int | None = None
    company: str | None = None
    count: int | None = None
    # Where the reading came from, so a wrong answer can be traced to the rule
    # or the model rather than argued about.
    source: str = "rules"


@dataclass
class Reply:
    text: str
    action: str
    campaign_id: int | None = None
    # True when the assistant changed something rather than just reported.
    acted: bool = False


# ------------------------------------------------------------------- rules


_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("start", re.compile(r"\b(start|begin|resume|carry on|continue|go ahead|send today)\b", re.I)),
    ("pause", re.compile(r"\b(pause|hold|wait|stop for now|halt)\b", re.I)),
    ("stop", re.compile(r"\b(stop (this |the )?campaign|cancel|abandon|end it)\b", re.I)),
    ("failed", re.compile(r"\b(fail(ed|ures)?|errors?|bounced|didn'?t send)\b", re.I)),
    ("duplicates", re.compile(r"\b(duplicates?|already contacted|skipped duplicates?)\b", re.I)),
    ("skipped", re.compile(r"\b(skipped|held back|not sent)\b", re.I)),
    ("today", re.compile(r"\b(today|so far today|left today|quota)\b", re.I)),
    ("remaining", re.compile(r"\b(remaining|left|how many|outstanding|still to)\b", re.I)),
    ("status", re.compile(r"\b(status|progress|how (is|are)|where are we|summary|update)\b", re.I)),
    ("help", re.compile(r"\b(help|what can you|commands?)\b", re.I)),
]

_COMPANY = re.compile(
    r"(?:about|with|for|to|happened (?:to|with)|why (?:was|is|did))\s+"
    r"(?:the company\s+)?['\"]?([A-Za-z0-9&.\- ]{3,60}?)['\"]?"
    r"\s*(?:\?|$|,|\.| skipped| fail| not)",
    re.I,
)

_COUNT = re.compile(r"\b(?:send|do|next)\s+(\d{1,2})\b", re.I)


def parse_rules(message: str) -> Intent | None:
    """The phrasings people actually type. No network, no cost, no ambiguity."""
    text = message.strip()
    if not text:
        return None

    company = _COMPANY.search(text)
    if company and not re.search(r"\b(start|pause|stop)\b", text, re.I):
        return Intent(action="company", company=company.group(1).strip())

    # "send 5", "send today's outreach", "send the next 10"
    count = _COUNT.search(text)
    if count and re.search(r"\bsend\b", text, re.I):
        return Intent(action="send", count=min(int(count.group(1)), 10))

    for action, pattern in _PATTERNS:
        if pattern.search(text):
            return Intent(action=action)
    return None


# ------------------------------------------------------------------- model


_SYSTEM = (
    "You classify one instruction about an email outreach campaign. "
    "Reply with JSON only, no prose, in the form "
    '{"action": "...", "company": null, "count": null}. '
    f"`action` must be exactly one of: {', '.join(ACTIONS)}. "
    "Use `company` when the person names a specific company. "
    "Use `count` when they say how many emails to send. "
    "If you are unsure, use \"help\"."
)


def parse_with_model(message: str) -> Intent | None:
    raw = providers.complete(f"Instruction: {message}", _SYSTEM, 120)
    if not raw:
        return None
    body = raw.strip()
    # Models like to wrap JSON in a fenced block however firmly they are asked.
    fence = re.search(r"\{.*\}", body, re.S)
    if not fence:
        return None
    try:
        data = json.loads(fence.group(0))
    except ValueError:
        return None
    action = str(data.get("action", "")).strip().lower()
    if action not in ACTIONS:
        # The one place a model could steer this thing somewhere it should not
        # go, closed: an action that is not on the list is not an action.
        log.info("Assistant model proposed an unknown action %r", action)
        return None
    count = data.get("count")
    return Intent(
        action=action,
        company=(str(data["company"]).strip() if data.get("company") else None),
        count=min(int(count), 10) if isinstance(count, (int, float)) else None,
        source="model",
    )


def parse(message: str) -> Intent:
    return parse_rules(message) or parse_with_model(message) or Intent(action="help")


# ----------------------------------------------------------------- answers


def active_campaign(db: Session, campaign_id: int | None = None) -> Campaign | None:
    """The campaign a bare instruction refers to.

    The one that is running, else the one most recently touched. Anything else
    would have "continue" pick a campaign at random, which is the sort of
    helpfulness that sends two hundred emails to the wrong list.
    """
    if campaign_id:
        return db.get(Campaign, campaign_id)
    running = db.scalar(
        select(Campaign)
        .where(Campaign.status.in_([CampaignStatus.running, CampaignStatus.daily_limit]))
        .order_by(Campaign.last_activity_at.desc().nullslast())
        .limit(1)
    )
    if running:
        return running
    return db.scalar(
        select(Campaign)
        .order_by(Campaign.last_activity_at.desc().nullslast(), Campaign.created_at.desc())
        .limit(1)
    )


def _status_lines(db: Session, campaign: Campaign) -> str:
    s = cm.snapshot(db, campaign)
    lines = [
        f"**{s['name']}** — {s['status'].value.replace('_', ' ')}",
        f"{s['sent']} sent to {s['companies_contacted']} companies · "
        f"{s['processed']} of {s['total']} processed ({s['percent']}%)",
        f"Today: {s['sent_today']} of {s['daily_limit']} · {s['remaining_today']} left",
    ]
    trouble = []
    if s["failed"]:
        trouble.append(f"{s['failed']} failed")
    if s["duplicates"]:
        trouble.append(f"{s['duplicates']} duplicates")
    if s["skipped"]:
        trouble.append(f"{s['skipped']} skipped")
    if s["unverified"]:
        trouble.append(f"{s['unverified']} unconfirmed")
    if s["awaiting_approval"]:
        trouble.append(f"{s['awaiting_approval']} waiting for you")
    if trouble:
        lines.append(" · ".join(trouble))
    if s["next_company"]:
        lines.append(f"Next: {s['next_company']}")
    return "\n".join(lines)


def _target_list(db: Session, campaign: Campaign, state: TargetState, label: str) -> str:
    rows = db.scalars(
        select(CampaignTarget)
        .where(CampaignTarget.campaign_id == campaign.id, CampaignTarget.state == state)
        .order_by(CampaignTarget.position)
        .limit(10)
    ).all()
    if not rows:
        return f"No {label} in **{campaign.name}**."
    total = db.scalar(
        select(cm.func.count(CampaignTarget.id)).where(
            CampaignTarget.campaign_id == campaign.id, CampaignTarget.state == state
        )
    )
    lines = [f"{total} {label} in **{campaign.name}**:"]
    for row in rows:
        detail = row.skip_reason or row.last_error or ""
        lines.append(f"· {row.company_name} ({row.email or 'no address'}){' — ' + detail if detail else ''}")
    if total > len(rows):
        lines.append(f"…and {total - len(rows)} more.")
    return "\n".join(lines)


HELP = (
    "I can run the campaign for you. Try:\n"
    "· **status** — where everything stands\n"
    "· **continue** or **start** — begin, or pick up where it stopped\n"
    "· **pause** — stop before the next email\n"
    "· **send 5** — advance a few and report back\n"
    "· **how many are left?**\n"
    "· **show failed** · **show duplicates** · **how many today?**\n"
    "· **why was ABC Coffee skipped?**"
)


def respond(db: Session, message: str, campaign_id: int | None = None) -> Reply:
    """One instruction in, one answer out — every figure read from the database."""
    intent = parse(message)
    campaign = active_campaign(db, campaign_id or intent.campaign_id)

    if intent.action == "help" or campaign is None:
        if campaign is None:
            return Reply(text="There are no campaigns yet. Upload a company file to begin.", action="help")
        return Reply(text=HELP, action="help")

    if intent.action == "status":
        return Reply(text=_status_lines(db, campaign), action="status", campaign_id=campaign.id)

    if intent.action == "today":
        q = cm.quota_state(db, campaign=campaign)
        return Reply(
            text=(
                f"{q['sent']} of {q['limit']} sent today, {q['remaining']} left. "
                + ("The day's allowance is spent." if not q["remaining"] else "")
            ).strip(),
            action="today",
            campaign_id=campaign.id,
        )

    if intent.action == "remaining":
        s = cm.snapshot(db, campaign)
        return Reply(
            text=(
                f"{s['remaining']} addresses still to go in **{s['name']}**, "
                f"out of {s['total']}. Next is {s['next_company'] or '—'}."
            ),
            action="remaining",
            campaign_id=campaign.id,
        )

    if intent.action in ("failed", "duplicates", "skipped"):
        state = {
            "failed": (TargetState.failed, "failed"),
            "duplicates": (TargetState.duplicate, "skipped as duplicates"),
            "skipped": (TargetState.skipped, "skipped"),
        }[intent.action]
        return Reply(
            text=_target_list(db, campaign, state[0], state[1]),
            action=intent.action,
            campaign_id=campaign.id,
        )

    if intent.action == "company":
        return Reply(text=_company_answer(db, intent.company or ""), action="company", campaign_id=campaign.id)

    if intent.action == "pause":
        try:
            cm.pause(db, campaign)
        except cm.TransitionError as exc:
            return Reply(text=str(exc), action="pause", campaign_id=campaign.id)
        return Reply(
            text=f"Paused **{campaign.name}**. Nothing further will be sent until you start it again.",
            action="pause",
            campaign_id=campaign.id,
            acted=True,
        )

    if intent.action == "stop":
        cm.stop(db, campaign)
        return Reply(
            text=f"Stopped **{campaign.name}** for good. The record is kept; remaining companies are cancelled.",
            action="stop",
            campaign_id=campaign.id,
            acted=True,
        )

    if intent.action in ("start", "send"):
        # Starting is all the assistant does here — the actual sending is
        # driven by the page, one company at a time, so that closing the tab
        # stops it. An assistant that could fire fifty emails from a sentence
        # is one bad interpretation away from an apology.
        try:
            cm.start(db, campaign)
        except cm.TransitionError as exc:
            return Reply(text=str(exc), action=intent.action, campaign_id=campaign.id)
        s = cm.snapshot(db, campaign)
        if s["status"] == CampaignStatus.completed:
            return Reply(text=f"**{campaign.name}** is finished — nothing left to send.", action="start", campaign_id=campaign.id)
        return Reply(
            text=(
                f"Running **{campaign.name}**, starting from {s['next_company']}. "
                f"{s['remaining_today']} of today's {s['daily_limit']} still available."
            ),
            action="start",
            campaign_id=campaign.id,
            acted=True,
        )

    return Reply(text=HELP, action="help", campaign_id=campaign.id)


def _company_answer(db: Session, name: str) -> str:
    """What happened to one company, across every campaign."""
    if not name:
        return "Which company?"
    like = f"%{name.strip().casefold()}%"
    rows = db.scalars(
        select(CampaignTarget)
        .where(cm.func.lower(CampaignTarget.company_name).like(like))
        .order_by(CampaignTarget.position)
        .limit(8)
    ).all()
    if not rows:
        return f"Nothing in any campaign matches “{name}”."

    lines = []
    for row in rows:
        state = row.state.value.replace("_", " ")
        detail = row.skip_reason or row.last_error or ""
        when = f" on {row.sent_at.strftime('%d %b %Y')}" if row.sent_at else ""
        lines.append(
            f"· **{row.company_name}** ({row.email or 'no address'}) — {state}{when}"
            + (f"\n  {detail}" if detail else "")
        )
    return "\n".join(lines)
