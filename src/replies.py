"""
Reply processing.

Reads your Gmail inbox (read-only), matches incoming mail against the outreach
records in the BeviGrow tracker, and proposes a status change:

    a genuine answer          -> Replied
    "come back in March"      -> Follow-up needed
    a clear no                -> Not interested
    out-of-office / bounce    -> left alone, flagged to you

Nothing is written to the tracker without your confirmation, and a company is
never marked "Not interested" just because nobody answered.
"""

from __future__ import annotations

from datetime import date

from src.config import settings
from src.logging_setup import console, get_logger
from src.models import TrackerStatus
from src.utils import days_from_now, domain_of, truncate
from src import approval, email_sender, llm, tracker as tracker_mod

log = get_logger("replies")

_AUTO_MARKERS = (
    "out of office", "auto-reply", "autoreply", "automatic reply", "abwesenheit",
    "abwesenheitsnotiz", "delivery status notification", "undeliverable",
    "mail delivery failed", "returned mail", "vacation reply", "je suis absent",
)


def _looks_automatic(subject: str, body: str) -> bool:
    haystack = f"{subject} {body[:500]}".lower()
    return any(marker in haystack for marker in _AUTO_MARKERS)


def _match_record(message: dict, records: list[dict]) -> dict | None:
    sender = (message.get("from_email") or "").lower()
    if not sender:
        return None
    sender_domain = domain_of(sender)

    for record in records:
        stored = (record.get("email") or "").lower()
        if stored and sender in stored:
            return record
    for record in records:
        if sender_domain and sender_domain == domain_of(record.get("website") or ""):
            return record
        stored = (record.get("email") or "").lower()
        if stored and sender_domain and sender_domain == domain_of(stored):
            return record
    return None


def _fallback_classification(subject: str, body: str) -> dict:
    """Used when Claude is unavailable - deliberately cautious."""
    low = f"{subject} {body}".lower()
    negative = ("not interested", "no interest", "kein interesse", "unsubscribe",
                "do not contact", "nicht kontaktieren", "we are not looking")
    later = ("later", "next season", "next year", "come back", "q1", "q2", "q3", "q4",
             "im not the right", "not the right person", "spaeter", "später")

    if any(word in low for word in negative):
        status = "not_interested"
    elif any(word in low for word in later):
        status = "follow_up_needed"
    else:
        status = "replied"

    return {
        "status": status,
        "summary": truncate(body.strip().replace("\n", " "), 200),
        "next_action": "Read the reply and answer.",
        "follow_up_in_days": settings.follow_up_days,
        "is_auto_reply": _looks_automatic(subject, body),
    }


def process(days: int = 30, interactive: bool = True, limit: int = 60) -> dict[str, int]:
    """Scan recent inbox mail and update matching tracker records."""
    client = tracker_mod.get_client()
    records = client.list_outreach(limit=500)
    if not records:
        console.print("[yellow]No outreach records in the tracker yet.[/yellow]")
        return {}

    try:
        inbox = email_sender.fetch_recent_replies(days=days, max_results=limit)
    except Exception as exc:
        console.print(f"[red]Could not read Gmail: {exc}[/red]")
        return {}

    counts = {"matched": 0, "updated": 0, "auto": 0, "ignored": 0}

    for message in inbox:
        record = _match_record(message, records)
        if not record:
            counts["ignored"] += 1
            continue
        counts["matched"] += 1

        subject = message.get("subject", "")
        body = message.get("body") or message.get("snippet", "")

        if _looks_automatic(subject, body):
            counts["auto"] += 1
            console.print(
                f"[dim]Auto-reply from {record.get('company_name')} - left unchanged.[/dim]"
            )
            continue

        if llm.available():
            try:
                verdict = llm.classify_reply(
                    record.get("company_name", ""), record.get("message_sent", ""), body
                )
            except Exception as exc:
                log.warning("Reply classification failed: %s", exc)
                verdict = _fallback_classification(subject, body)
        else:
            verdict = _fallback_classification(subject, body)

        if verdict.get("is_auto_reply") or verdict.get("status") == "unclear":
            counts["auto"] += 1
            continue

        status_map = {
            "replied": TrackerStatus.REPLIED,
            "not_interested": TrackerStatus.NOT_INTERESTED,
            "follow_up_needed": TrackerStatus.FOLLOW_UP_NEEDED,
        }
        new_status = status_map.get(verdict.get("status", ""), TrackerStatus.REPLIED)

        console.rule(f"[bold]{record.get('company_name')}")
        console.print(f"[dim]From:[/dim] {message.get('from')}")
        console.print(f"[dim]Subject:[/dim] {subject}")
        console.print(f"[dim]Reply:[/dim] {truncate(body, 700)}")
        console.print(f"[cyan]Proposed status:[/cyan] {new_status.value}")
        console.print(f"[cyan]Summary:[/cyan] {verdict.get('summary', '')}")
        console.print(f"[cyan]Next action:[/cyan] {verdict.get('next_action', '')}")

        if interactive and not approval.confirm("Apply this to the tracker?", default=True):
            counts["ignored"] += 1
            continue

        patch = {
            "status": new_status.value,
            "their_reply": truncate(body, 4000),
            "replied_on": date.today().isoformat(),
            "next_action": verdict.get("next_action", "") or None,
        }
        if new_status is TrackerStatus.FOLLOW_UP_NEEDED:
            patch["next_follow_up"] = days_from_now(
                int(verdict.get("follow_up_in_days") or settings.follow_up_days)
            )
        elif new_status is TrackerStatus.NOT_INTERESTED:
            patch["next_follow_up"] = None

        try:
            client.update_outreach(record["id"], patch)
            counts["updated"] += 1
            console.print(f"[green]Tracker record #{record['id']} updated.[/green]")
        except Exception as exc:
            log.error("Could not update record #%s: %s", record.get("id"), exc)

    console.print(
        f"\n[bold]Replies:[/bold] {counts['matched']} matched, {counts['updated']} updated, "
        f"{counts['auto']} auto-replies, {counts['ignored']} ignored"
    )
    return counts
