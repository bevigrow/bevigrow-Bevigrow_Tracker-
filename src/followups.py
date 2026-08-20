"""
Follow-up management.

The tracker already knows which records are due - the API exposes
GET /api/outreach?due=true - so this module asks it, prepares the follow-up
message, and (only with your approval) sends it and updates the record.

Nothing is ever sent automatically. FOLLOW_UP_APPROVAL_REQUIRED=true in .env
enforces that, and FOLLOW_UP_DAYS controls the interval.
"""

from __future__ import annotations

import re
from datetime import date

from src.config import settings
from src.logging_setup import console, get_logger
from src.models import (
    Channel,
    CompanyInput,
    PersonCandidate,
    Priority,
    Relevance,
    ResearchResult,
    TrackerStatus,
)
from src.utils import days_from_now, parse_date
from src import approval, email_generator, email_sender, tracker as tracker_mod

log = get_logger("followups")


def research_from_record(record: dict) -> ResearchResult:
    """A light ResearchResult rebuilt from a tracker row - no new research needed."""
    result = ResearchResult(
        company_input=CompanyInput(
            company=record.get("company_name", ""),
            country=record.get("country", "") or "",
        ),
        resolved_company_name=record.get("company_name", ""),
        website=record.get("website") or "",
        country=record.get("country") or "",
        description="",
        relevance=Relevance(priority=Priority.UNCERTAIN, reason="from an existing tracker record"),
    )
    return result


def person_from_record(record: dict) -> PersonCandidate | None:
    name = (record.get("contact_person") or "").strip()
    if not name:
        return None
    return PersonCandidate(name=name, title="", email=record.get("email") or "", score=50)


def original_subject(record: dict) -> str:
    message = record.get("message_sent") or ""
    match = re.search(r"^Subject:\s*(.+)$", message, re.M)
    if match:
        return re.sub(r"^(Re|RE|AW|Fwd):\s*", "", match.group(1).strip())
    return "Indian Green Coffee - BeviGrow"


def due_records(limit: int = 200) -> list[dict]:
    """Records whose next follow-up date has arrived."""
    client = tracker_mod.get_client()
    records = client.due_follow_ups(limit=limit)

    skip_statuses = {
        TrackerStatus.REPLIED.value,
        TrackerStatus.NOT_INTERESTED.value,
    }
    out = []
    for record in records:
        if record.get("status") in skip_statuses:
            continue
        out.append(record)
    return out


def show_due(records: list[dict]) -> None:
    from rich.table import Table

    if not records:
        console.print("[green]Nothing is due for follow-up today.[/green]")
        return

    table = Table(title=f"{len(records)} follow-ups due", header_style="bold")
    table.add_column("#", justify="right")
    table.add_column("Company", overflow="fold")
    table.add_column("Channel")
    table.add_column("Contacted")
    table.add_column("Due")
    table.add_column("Status")
    table.add_column("Sent so far", justify="right")

    for record in records:
        table.add_row(
            str(record.get("id")),
            record.get("company_name", ""),
            record.get("contact_method", ""),
            record.get("contacted_on") or "-",
            record.get("next_follow_up") or "-",
            record.get("status", ""),
            str(record.get("follow_ups_sent", 0)),
        )
    console.print(table)


def process(interactive: bool = True, limit: int | None = None,
            max_follow_ups: int = 2) -> dict[str, int]:
    """
    Walk through everything that is due.

    A record that has already had `max_follow_ups` chases is marked
    "no response" instead of being chased again.
    """
    client = tracker_mod.get_client()
    records = due_records()
    if limit:
        records = records[:limit]

    show_due(records)
    counts = {"sent": 0, "simulated": 0, "skipped": 0, "closed": 0, "failed": 0}

    for record in records:
        record_id = record.get("id")
        company = record.get("company_name", "")
        console.rule(f"[bold]Follow-up: {company}")

        # Enough is enough.
        if (record.get("follow_ups_sent") or 0) >= max_follow_ups:
            console.print(
                f"[dim]{company} has already had {record['follow_ups_sent']} follow-ups - "
                "marking as no response.[/dim]"
            )
            try:
                client.update_outreach(
                    record_id,
                    {
                        "status": TrackerStatus.NO_RESPONSE.value,
                        "next_action": "No response after the agreed number of follow-ups.",
                        "next_follow_up": None,
                    },
                )
                counts["closed"] += 1
            except Exception as exc:
                log.error("Could not close record #%s: %s", record_id, exc)
                counts["failed"] += 1
            continue

        if record.get("contact_method") != Channel.EMAIL.value:
            console.print(
                f"[yellow]{company} was contacted via {record.get('contact_method')} - "
                f"follow up manually at {record.get('contact_point') or '(no link stored)'}.[/yellow]"
            )
            counts["skipped"] += 1
            continue

        to = [a.strip() for a in (record.get("email") or "").split(",") if a.strip()]
        if not to:
            console.print(f"[yellow]{company} has no email address stored - skipping.[/yellow]")
            counts["skipped"] += 1
            continue

        research = research_from_record(record)
        person = person_from_record(record)
        try:
            message = email_generator.build_followup(
                research, person, to,
                original_subject=original_subject(record),
                date_contacted=record.get("contacted_on") or "our earlier message",
            )
        except Exception as exc:
            log.error("Could not build the follow-up for %s: %s", company, exc)
            counts["failed"] += 1
            continue

        if interactive and settings.follow_up_approval_required:
            decision, message = approval.ask(
                message,
                f"Follow-up #{(record.get('follow_ups_sent') or 0) + 1} for {company}. "
                f"Originally contacted {record.get('contacted_on') or 'unknown date'}.",
            )
            if decision == "skip":
                counts["skipped"] += 1
                continue
            if decision == "quit":
                break
        elif settings.follow_up_approval_required:
            console.print(f"[yellow]{company}: follow-up prepared but approval is required.[/yellow]")
            counts["skipped"] += 1
            continue

        send_result = email_sender.send(message, company)
        if not send_result.ok:
            console.print(f"[red]Follow-up failed: {send_result.error}[/red]")
            counts["failed"] += 1
            continue

        counts["simulated" if send_result.simulated else "sent"] += 1

        # Record it: the API bumps follow_ups_sent and moves the next date for us.
        try:
            client.log_follow_up(record_id, days_until_next=settings.follow_up_days)
            existing = record.get("message_sent") or ""
            client.update_outreach(
                record_id,
                {
                    "status": TrackerStatus.FOLLOW_UP_SENT.value,
                    "message_sent": (
                        f"{existing}\n\n--- FOLLOW-UP {date.today().isoformat()} ---\n"
                        f"Subject: {message.subject}\n\n{message.body}"
                    )[:60000],
                    "next_action": f"Wait for a reply; next chase {days_from_now(settings.follow_up_days)}",
                },
            )
            console.print(f"[green]Tracker record #{record_id} updated.[/green]")
        except Exception as exc:
            log.error("Follow-up sent but the tracker update failed for #%s: %s", record_id, exc)
            counts["failed"] += 1

    console.print(
        f"\n[bold]Follow-ups:[/bold] {counts['sent']} sent, {counts['simulated']} simulated, "
        f"{counts['skipped']} skipped, {counts['closed']} closed, {counts['failed']} failed"
    )
    return counts


def upcoming(days_ahead: int = 14) -> list[dict]:
    """Everything with a follow-up date inside the next N days."""
    client = tracker_mod.get_client()
    records = client.list_outreach(limit=500)
    cutoff = date.today()
    out = []
    for record in records:
        due = parse_date(record.get("next_follow_up"))
        if not due:
            continue
        delta = (due - cutoff).days
        if 0 <= delta <= days_ahead and record.get("status") not in {
            TrackerStatus.REPLIED.value,
            TrackerStatus.NOT_INTERESTED.value,
        }:
            out.append(record)
    return sorted(out, key=lambda r: r.get("next_follow_up") or "")
