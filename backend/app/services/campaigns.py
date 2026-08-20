"""Campaign state: the queue, the daily ceiling, and the start/stop switch.

This module is the part the AI cannot argue with.

The assistant decides what an email should *say*. It never decides who is next,
whether a company has been written to before, or whether there is quota left —
those are the three questions that, answered wrongly, email a real customer
twice or send 200 messages in an afternoon from an account that is supposed to
look like a person typing. So they are answered here, in SQL, by functions the
assistant can only call and never bypass.

Two decisions worth knowing about:

*Position is derived, not stored.* "Where did it stop?" is answered by "the
lowest-numbered target still pending", not by a cursor column. A stored cursor
is a second source of truth that drifts the first time a send is retried out of
order, and when it drifts it re-sends. The queue rows *are* the position.

*A quota slot is spent when it is reserved, not when the send succeeds.* If the
process dies between reserving and sending, the slot stays spent. That errs
towards sending 49 rather than 51, which is the direction a limit should fail.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import (
    TARGET_TERMINAL,
    Campaign,
    CampaignEvent,
    CampaignStatus,
    CampaignTarget,
    DailyQuota,
    EmailAccount,
    SendMode,
    TargetState,
)

log = logging.getLogger("bevigrow.campaigns")

# The account-wide ceiling. A campaign may ask for less; it can never ask for
# more, and the constant is not reachable from any API surface.
HARD_DAILY_CAP = 50


# ------------------------------------------------------------------- the day


def sending_day(now: datetime | None = None) -> date:
    """Which day a send counts against.

    Offset from UTC so "today" means the operator's today — IST by default. A
    campaign that spends its fifty at 9pm in Kerala should reset at midnight
    there, not at 5:30am when UTC rolls over.
    """
    moment = now or datetime.now(timezone.utc)
    return (moment + timedelta(minutes=settings.OUTREACH_DAY_OFFSET_MINUTES)).date()


# ------------------------------------------------------------------- events


def record(db: Session, campaign_id: int, kind: str, message: str, target_id: int | None = None) -> None:
    """Append one line to the campaign's operational log.

    Deliberately not flushed on its own — it rides the caller's transaction, so
    an event never claims something the same transaction went on to roll back.
    """
    db.add(
        CampaignEvent(
            campaign_id=campaign_id, kind=kind, message=message[:600], target_id=target_id
        )
    )


# -------------------------------------------------------------------- quota


def quota_row(db: Session, *, account_id: int, day: date | None = None, limit: int | None = None) -> DailyQuota:
    """Today's quota record, created on first use, locked for update.

    The lock is what makes the ceiling real: two requests that both read 49
    would both send. Postgres takes a row lock; SQLite has no row locks but
    also no concurrency worth the name, so it skips it.
    """
    when = day or sending_day()
    stmt = select(DailyQuota).where(DailyQuota.day == when, DailyQuota.account_id == account_id)
    if not settings.is_sqlite:
        stmt = stmt.with_for_update()
    row = db.scalar(stmt)
    if row is None:
        row = DailyQuota(
            day=when,
            account_id=account_id,
            limit_value=min(limit or HARD_DAILY_CAP, HARD_DAILY_CAP),
        )
        db.add(row)
        db.flush()
    return row


def default_account_id(db: Session) -> int:
    """The mailbox quotas are counted against.

    Resolved rather than defaulted to 0: the engine reserves slots against the
    real account id, so a status panel reading account 0 would cheerfully
    report "0 of 50 sent today" directly underneath fifty sent emails.
    """
    row = db.scalar(
        select(EmailAccount.id).order_by(EmailAccount.is_default.desc(), EmailAccount.id.asc()).limit(1)
    )
    return row or 0


def quota_state(db: Session, *, account_id: int | None = None, campaign: Campaign | None = None) -> dict:
    """Read-only view of today's allowance. Never mutates, never locks."""
    if account_id is None:
        account_id = default_account_id(db)
    when = sending_day()
    row = db.scalar(
        select(DailyQuota).where(DailyQuota.day == when, DailyQuota.account_id == account_id)
    )
    ceiling = effective_limit(campaign)
    sent = row.sent_count if row else 0
    return {
        "day": when,
        "limit": ceiling,
        "sent": sent,
        "failed": row.failed_count if row else 0,
        "remaining": max(0, ceiling - sent),
    }


def effective_limit(campaign: Campaign | None) -> int:
    """The smaller of what the campaign asked for and what is allowed."""
    if campaign is None:
        return HARD_DAILY_CAP
    return max(0, min(campaign.daily_limit or HARD_DAILY_CAP, HARD_DAILY_CAP))


def reserve_slot(db: Session, *, account_id: int, campaign: Campaign) -> bool:
    """Take one send off today's allowance. False means the day is spent.

    Call inside the same transaction as the send record. The counter moves
    before the email leaves, so a crash costs a slot rather than the limit.
    """
    ceiling = effective_limit(campaign)
    row = quota_row(db, account_id=account_id, limit=ceiling)
    # The campaign's own limit can be lower than the stored one; honour the
    # tighter of the two on every check rather than trusting the stored value.
    if row.sent_count >= min(row.limit_value, ceiling):
        return False
    row.sent_count += 1
    row.limit_value = min(row.limit_value, ceiling) if row.limit_value else ceiling
    return True


def release_slot(db: Session, *, account_id: int, failed: bool = True) -> None:
    """Hand a reserved slot back after a send that never left.

    Only for a failure the mail server reported synchronously — never for a
    send whose outcome is unknown, because an unknown may well have arrived.
    """
    row = quota_row(db, account_id=account_id)
    if row.sent_count > 0:
        row.sent_count -= 1
    if failed:
        row.failed_count += 1


# ----------------------------------------------------------------- the queue


def next_target(db: Session, campaign: Campaign) -> CampaignTarget | None:
    """The company the campaign would work on next. Pure read, no lock.

    For display and for answering "what's next?". The sender uses
    `claim_next_target` instead, which is the same query with teeth.
    """
    return db.scalar(
        select(CampaignTarget)
        .where(
            CampaignTarget.campaign_id == campaign.id,
            CampaignTarget.state == TargetState.pending,
        )
        .order_by(CampaignTarget.position.asc())
        .limit(1)
    )


def claim_next_target(db: Session, campaign: Campaign) -> CampaignTarget | None:
    """Take the next address, locking it against anyone else taking it too.

    The background scheduler and a person pressing Send can both reach for the
    same row within milliseconds of each other, and two claims on one row is
    two identical emails to one buyer. Postgres hands the row to whichever
    transaction arrives first and gives the other the row after it —
    SKIP LOCKED rather than a wait, because the second caller wants the next
    company, not this one a moment later.

    SQLite has neither, and also no concurrency: one process, one thread at a
    time, so the plain read is already exclusive.
    """
    stmt = (
        select(CampaignTarget)
        .where(
            CampaignTarget.campaign_id == campaign.id,
            CampaignTarget.state == TargetState.pending,
        )
        .order_by(CampaignTarget.position.asc())
        .limit(1)
    )
    if not settings.is_sqlite:
        stmt = stmt.with_for_update(skip_locked=True)
    return db.scalar(stmt)


def company_counts(db: Session, campaign: Campaign) -> dict:
    """Companies behind the addresses, so a summary can say both.

    The queue is one row per address; a person thinks in companies. Reporting
    only rows would claim 68 companies contacted when it was 61 companies and
    seven of them had a second mailbox.
    """
    companies = db.scalar(
        select(func.count(func.distinct(CampaignTarget.normalized_company))).where(
            CampaignTarget.campaign_id == campaign.id
        )
    ) or 0
    contacted = db.scalar(
        select(func.count(func.distinct(CampaignTarget.normalized_company))).where(
            CampaignTarget.campaign_id == campaign.id,
            CampaignTarget.state == TargetState.sent,
        )
    ) or 0
    # Companies whose row count exceeds one — the ones worth naming in a summary.
    multi = db.scalar(
        select(func.count()).select_from(
            select(CampaignTarget.normalized_company)
            .where(CampaignTarget.campaign_id == campaign.id)
            .group_by(CampaignTarget.normalized_company)
            .having(func.count(CampaignTarget.id) > 1)
            .subquery()
        )
    ) or 0
    return {"companies": companies, "companies_contacted": contacted, "multi_address": multi}


def state_counts(db: Session, campaign: Campaign) -> dict[TargetState, int]:
    rows = db.execute(
        select(CampaignTarget.state, func.count(CampaignTarget.id))
        .where(CampaignTarget.campaign_id == campaign.id)
        .group_by(CampaignTarget.state)
    ).all()
    return {state: count for state, count in rows}


def snapshot(db: Session, campaign: Campaign) -> dict:
    """Everything the status panel and the assistant both read.

    One function, so a number quoted in chat and the same number on screen
    cannot disagree — they are the same query.
    """
    counts = state_counts(db, campaign)
    total = sum(counts.values())
    sent = counts.get(TargetState.sent, 0)
    failed = counts.get(TargetState.failed, 0)
    duplicates = counts.get(TargetState.duplicate, 0)
    skipped = counts.get(TargetState.skipped, 0)
    unverified = counts.get(TargetState.unverified, 0)
    awaiting = counts.get(TargetState.awaiting_approval, 0)
    pending = counts.get(TargetState.pending, 0)
    processed = total - pending - awaiting

    companies = company_counts(db, campaign)
    upcoming = next_target(db, campaign)
    last = (
        db.get(CampaignTarget, campaign.last_target_id) if campaign.last_target_id else None
    )
    quota = quota_state(db, campaign=campaign)

    return {
        "campaign_id": campaign.id,
        "name": campaign.name,
        "status": campaign.status,
        "mode": campaign.mode,
        # `total` counts addresses; `companies` counts the businesses behind
        # them. Both are shown, because "50 sent" and "50 companies reached"
        # are different claims and only one of them is true.
        "total": total,
        "companies": companies["companies"],
        "companies_contacted": companies["companies_contacted"],
        "multi_address_companies": companies["multi_address"],
        "processed": processed,
        "sent": sent,
        "failed": failed,
        "duplicates": duplicates,
        "skipped": skipped,
        "unverified": unverified,
        "awaiting_approval": awaiting,
        "remaining": pending,
        "percent": round(processed / total * 100, 1) if total else 0.0,
        "daily_limit": quota["limit"],
        "sent_today": quota["sent"],
        "remaining_today": quota["remaining"],
        "last_company": last.company_name if last else None,
        "next_company": upcoming.company_name if upcoming else None,
        "next_target_id": upcoming.id if upcoming else None,
        "last_activity_at": campaign.last_activity_at,
    }


# --------------------------------------------------------------- the switch


class TransitionError(Exception):
    """A start/pause/stop that does not make sense from where the campaign is."""


def start(db: Session, campaign: Campaign) -> Campaign:
    """Begin, or pick up again after a pause or a spent day."""
    if campaign.status == CampaignStatus.completed:
        raise TransitionError("This campaign has already finished.")
    if campaign.status == CampaignStatus.stopped:
        raise TransitionError("This campaign was stopped. Create a new one to send again.")
    if next_target(db, campaign) is None:
        campaign.status = CampaignStatus.completed
        record(db, campaign.id, "completed", "Nothing left to send.")
        db.commit()
        return campaign

    was = campaign.status
    campaign.status = CampaignStatus.running
    campaign.last_activity_at = datetime.now(timezone.utc)
    record(
        db,
        campaign.id,
        "started",
        "Resumed" if was in (CampaignStatus.paused, CampaignStatus.daily_limit) else "Started",
    )
    db.commit()
    return campaign


def pause(db: Session, campaign: Campaign, reason: str = "Paused by hand") -> Campaign:
    """Stop before the next email. Anything mid-flight is left to finish.

    Nothing is discarded: the queue, the drafts and the position all stay, so
    resuming is the same operation as starting.
    """
    if campaign.status not in (CampaignStatus.running, CampaignStatus.daily_limit):
        raise TransitionError("This campaign is not running.")
    campaign.status = CampaignStatus.paused
    campaign.last_activity_at = datetime.now(timezone.utc)
    record(db, campaign.id, "paused", reason)
    db.commit()
    return campaign


def stop(db: Session, campaign: Campaign) -> Campaign:
    """End it for good. Pending companies are cancelled, history is kept."""
    db.query(CampaignTarget).filter(
        CampaignTarget.campaign_id == campaign.id,
        CampaignTarget.state.in_([TargetState.pending, TargetState.awaiting_approval]),
    ).update({CampaignTarget.state: TargetState.cancelled}, synchronize_session=False)
    campaign.status = CampaignStatus.stopped
    campaign.last_activity_at = datetime.now(timezone.utc)
    record(db, campaign.id, "stopped", "Stopped by hand; remaining companies cancelled.")
    db.commit()
    return campaign


def mark_limit_reached(db: Session, campaign: Campaign) -> None:
    """Park the campaign until tomorrow. Distinct from a pause on purpose.

    `paused` means a person stopped it and a person restarts it.
    `daily_limit` means the day is spent and tomorrow it may carry on by
    itself — the difference is the whole reason "continue" can be automatic.
    """
    if campaign.status == CampaignStatus.running:
        campaign.status = CampaignStatus.daily_limit
        record(db, campaign.id, "daily_limit", "Daily sending limit reached.")


def refresh_completion(db: Session, campaign: Campaign) -> None:
    """Close the campaign once the queue holds nothing workable."""
    if campaign.status in (CampaignStatus.stopped, CampaignStatus.completed):
        return
    counts = state_counts(db, campaign)
    open_states = counts.get(TargetState.pending, 0) + counts.get(TargetState.awaiting_approval, 0)
    if open_states == 0:
        campaign.status = CampaignStatus.completed
        record(db, campaign.id, "completed", "All companies processed.")


def is_workable(campaign: Campaign) -> bool:
    """Whether the engine may take another step on this campaign right now."""
    return campaign.status == CampaignStatus.running


def resumable_today(db: Session, campaign: Campaign) -> bool:
    """A campaign parked on yesterday's limit that today could carry on."""
    if campaign.status != CampaignStatus.daily_limit:
        return False
    return quota_state(db, campaign=campaign)["remaining"] > 0


__all__ = [
    "HARD_DAILY_CAP",
    "TransitionError",
    "effective_limit",
    "is_workable",
    "mark_limit_reached",
    "claim_next_target",
    "next_target",
    "pause",
    "quota_state",
    "record",
    "refresh_completion",
    "release_slot",
    "reserve_slot",
    "resumable_today",
    "sending_day",
    "snapshot",
    "start",
    "state_counts",
    "stop",
    "SendMode",
]
