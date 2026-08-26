"""One company, one decision, one result, one log entry — then stop.

The whole automation is this function called repeatedly. It never loops over a
batch, because a batch is a transaction that can half-happen: forty emails out,
the process dies, and nothing on disk says which forty. Each call takes exactly
one address as far as it can go and commits, so the worst a crash can cost is
one message, and the queue always knows where it was.

The order below is the order in the spec, and it matters:

    is it a duplicate?  ->  is there quota?  ->  send  ->  did it work?
       ->  write the outreach record  ->  only then move on

The outreach record is written after a successful send and never before. A row
saying "contacted" for a message that failed is worse than no row, because the
duplicate check believes it.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import (
    AttemptStatus,
    Campaign,
    CampaignStatus,
    CampaignTarget,
    ContactMethod,
    EmailAccount,
    Outreach,
    OutreachStatus,
    SendAttempt,
    SendLedger,
    SendMode,
    TargetState,
)
from . import campaigns as cm
from . import duplicates, sender, templating

log = logging.getLogger("bevigrow.engine")


class StepOutcome:
    """What one step did, in words the chat and the UI both use."""

    def __init__(self, action: str, message: str, target: CampaignTarget | None = None):
        self.action = action          # sent | prepared | duplicate | skipped | failed | idle
        self.message = message
        self.target = target

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<StepOutcome {self.action}: {self.message}>"

    @property
    def as_dict(self) -> dict:
        return {
            "action": self.action,
            "message": self.message,
            "company": self.target.company_name if self.target else None,
            "email": self.target.email if self.target else None,
        }


def active_account(db: Session) -> EmailAccount | None:
    return db.scalar(
        select(EmailAccount).order_by(EmailAccount.is_default.desc(), EmailAccount.id.asc()).limit(1)
    )


def _ledger(
    db: Session,
    campaign: Campaign,
    target: CampaignTarget,
    outcome: str,
    reason: str | None = None,
    message_id: str | None = None,
) -> None:
    """Write one line of permanent history.

    Called for every decision that ends a target's life — sent, failed,
    duplicate, skipped. It copies the company's details rather than pointing at
    them, so deleting the campaign tomorrow leaves today's report intact. That
    is the whole point: without it, clearing out a morning of test runs also
    clears the agent's memory of having written to those companies.
    """
    db.add(
        SendLedger(
            day=cm.sending_day(),
            campaign_id=campaign.id,
            campaign_name=campaign.name,
            company_name=target.company_name,
            normalized_company=target.normalized_company,
            location=target.location,
            country=target.country,
            email=target.email,
            domain=target.domain,
            website=target.website,
            outcome=outcome,
            reason=(reason or "")[:400] or None,
            subject=target.prepared_subject,
            message_id=message_id,
        )
    )


def step(db: Session, campaign: Campaign, *, account: EmailAccount | None = None) -> StepOutcome:
    """Advance one campaign by exactly one address."""
    if campaign.status == CampaignStatus.daily_limit and cm.resumable_today(db, campaign):
        # A new day, and the campaign parked itself yesterday. It may carry on
        # without anyone pressing anything — that is the difference between
        # "paused" (a person stopped it) and "the day ran out".
        campaign.status = CampaignStatus.running
        cm.record(db, campaign.id, "resumed", "New day, quota available again.")
        db.commit()

    if not cm.is_workable(campaign):
        return StepOutcome("idle", f"Campaign is {campaign.status.value}.")

    # Claimed, not merely read: the scheduler and a person pressing Send
    # can reach for the same row at the same moment.
    target = cm.claim_next_target(db, campaign)
    if target is None:
        cm.refresh_completion(db, campaign)
        db.commit()
        return StepOutcome("idle", "Nothing left in the queue.")

    account = account or active_account(db)
    if account is None:
        cm.pause(db, campaign, "No sending mailbox is connected.")
        return StepOutcome("idle", "No sending mailbox is connected. Add one in Settings.")

    # --- nothing to send to -------------------------------------------------
    if not target.email:
        target.state = TargetState.skipped
        target.skip_reason = target.skip_reason or "No email address."
        campaign.last_target_id = target.id
        campaign.last_activity_at = datetime.now(timezone.utc)
        cm.record(db, campaign.id, "skipped", f"{target.company_name}: no address.", target.id)
        _ledger(db, campaign, target, "skipped", target.skip_reason)
        cm.refresh_completion(db, campaign)
        db.commit()
        return StepOutcome("skipped", f"{target.company_name} has no email address.", target)

    # --- already spoken to --------------------------------------------------
    verdict = duplicates.check(
        db, target,
        allow_recontact=campaign.allow_recontact,
        allow_resend=target.is_resend_approved
    )
    if verdict.is_duplicate:
        target.state = TargetState.duplicate
        target.skip_reason = verdict.reason
        target.duplicate_of_outreach_id = verdict.outreach_id
        campaign.last_target_id = target.id
        campaign.last_activity_at = datetime.now(timezone.utc)
        db.add(
            SendAttempt(
                campaign_id=campaign.id,
                target_id=target.id,
                to_email=target.email,
                status=AttemptStatus.duplicate_skipped,
                error=verdict.reason,
                finished_at=datetime.now(timezone.utc),
            )
        )
        cm.record(db, campaign.id, "duplicate", f"{target.company_name}: {verdict.reason}", target.id)
        _ledger(db, campaign, target, "duplicate", verdict.reason)
        cm.refresh_completion(db, campaign)
        db.commit()
        return StepOutcome("duplicate", f"{target.company_name} skipped — {verdict.reason}", target)

    # --- write the email ----------------------------------------------------
    if not target.prepared_body:
        missing = templating.unfilled_tokens(campaign, target)
        if missing:
            # "Dear #COMPANY_TEAM," arriving at a real buyer is the most
            # embarrassing thing this system could do. It stops instead, names
            # the placeholder, and moves on to the next company.
            target.state = TargetState.skipped
            target.skip_reason = (
                "The template needs " + ", ".join(f"#{t}" for t in missing) + ", "
                "and this row has no value for it."
            )
            campaign.last_target_id = target.id
            campaign.last_activity_at = datetime.now(timezone.utc)
            cm.record(
                db, campaign.id, "skipped", f"{target.company_name}: {target.skip_reason}", target.id
            )
            _ledger(db, campaign, target, "skipped", target.skip_reason)
            cm.refresh_completion(db, campaign)
            db.commit()
            return StepOutcome("skipped", f"{target.company_name}: {target.skip_reason}", target)

        subject, body = templating.render(campaign, target)
        target.prepared_subject = subject
        target.prepared_body = body
        target.prepared_at = datetime.now(timezone.utc)

    # --- a person approves first, in manual mode ----------------------------
    if campaign.mode == SendMode.manual:
        target.state = TargetState.awaiting_approval
        campaign.last_activity_at = datetime.now(timezone.utc)
        cm.record(db, campaign.id, "prepared", f"{target.company_name}: draft ready.", target.id)
        db.commit()
        return StepOutcome(
            "prepared", f"Draft ready for {target.company_name} — waiting for your approval.", target
        )

    return dispatch(db, campaign, target, account)


def dispatch(
    db: Session, campaign: Campaign, target: CampaignTarget, account: EmailAccount
) -> StepOutcome:
    """Actually send one prepared email, and record what happened.

    Also the path an approved draft takes, which is why it is separate: an
    approval must go through the same quota check and the same crash-safety as
    an automatic send, not a shortcut around them.
    """
    if not cm.reserve_slot(db, account_id=account.id, campaign=campaign):
        cm.mark_limit_reached(db, campaign)
        db.add(
            SendAttempt(
                campaign_id=campaign.id,
                target_id=target.id,
                to_email=target.email,
                status=AttemptStatus.daily_limit,
                error="Daily sending limit reached.",
                finished_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
        quota = cm.quota_state(db, account_id=account.id, campaign=campaign)
        return StepOutcome(
            "idle",
            f"Daily limit reached — {quota['sent']} of {quota['limit']} sent today. "
            f"Next up tomorrow: {target.company_name}.",
            target,
        )

    # Written and committed BEFORE the send, so a crash mid-flight leaves
    # evidence. On restart these become `unverified` rather than being retried:
    # the message may well have gone, and a second copy is the one mistake this
    # system must not make.
    message_id = sender.new_message_id(account)
    attempt = SendAttempt(
        campaign_id=campaign.id,
        target_id=target.id,
        attempt_no=target.attempts + 1,
        to_email=target.email,
        subject=target.prepared_subject,
        status=AttemptStatus.processing,
        message_id=message_id,
    )
    db.add(attempt)
    target.state = TargetState.processing
    target.attempts += 1
    db.commit()

    outcome = sender.send(
        account, target.email, target.prepared_subject or "", target.prepared_body or "", message_id
    )
    now = datetime.now(timezone.utc)
    attempt.finished_at = now

    if outcome.ok:
        attempt.status = AttemptStatus.sent
        attempt.provider_response = outcome.provider_response
        target.state = TargetState.sent
        target.sent_at = now
        target.last_error = None
        row = _log_outreach(db, campaign, target, account)
        target.outreach_id = row.id
        campaign.last_target_id = target.id
        campaign.last_activity_at = now
        cm.record(db, campaign.id, "sent", f"Emailed {target.company_name} at {target.email}.", target.id)
        _ledger(db, campaign, target, "sent", None, message_id)
        cm.refresh_completion(db, campaign)
        db.commit()
        quota = cm.quota_state(db, account_id=account.id, campaign=campaign)
        return StepOutcome(
            "sent",
            f"Sent to {target.company_name} ({target.email}). "
            f"{quota['sent']} of {quota['limit']} today.",
            target,
        )

    # Failure: the slot goes back, because nothing left the building.
    cm.release_slot(db, account_id=account.id, failed=True)
    target.state = TargetState.failed
    target.last_error = outcome.error
    attempt.error = outcome.error
    attempt.status = (
        AttemptStatus.invalid_email
        if outcome.recipient_fault
        else AttemptStatus.auth_error
        if outcome.auth_fault
        else AttemptStatus.failed
    )
    campaign.last_target_id = target.id
    campaign.last_activity_at = now
    cm.record(db, campaign.id, "failed", f"{target.company_name}: {outcome.error}", target.id)
    _ledger(db, campaign, target, "failed", outcome.error, message_id)

    # One bad address must not stop the campaign; a bad password must. Every
    # remaining company would otherwise be marched through and marked failed.
    if outcome.auth_fault:
        cm.pause(db, campaign, "Sending paused: the mailbox rejected the sign-in.")
        db.commit()
        return StepOutcome("failed", f"Paused — {outcome.error}", target)

    db.commit()
    return StepOutcome("failed", f"{target.company_name} failed: {outcome.error}", target)


def _log_outreach(
    db: Session, campaign: Campaign, target: CampaignTarget, account: EmailAccount
) -> Outreach:
    """Write the Log Outreach row, immediately, with the message as sent.

    One row per *company*, not per address. Each mailbox gets its own email —
    they are separate envelopes and fail separately — but a firm listing
    info@ and sales@ is one company to read about, and two rows identical in
    every visible respect look like the same company entered twice.

    So a second address at a company already written to on this campaign
    appends itself to the existing row instead of making a new one. Whoever
    replies is matched by their own address regardless, because the reply
    reader matches on the Message-ID of the individual email that was sent.

    The exact personalised text, not the template: six months from now the
    question is "what did we actually say to them", and a template full of
    placeholders cannot answer it. The subject line rides along at the top,
    because an email is its subject plus its body and a record holding only
    half of it is a record you cannot reconstruct.
    """
    sent_at = datetime.now(timezone.utc)
    local = sent_at + timedelta(minutes=settings.OUTREACH_DAY_OFFSET_MINUTES)
    body = target.prepared_body or ""
    subject = target.prepared_subject or ""
    # "Albrecht & Dill GmbH, Brandstücken 23, 22549 Hamburg" — the address
    # rides along with the name in the log, because two firms with similar
    # names are told apart by where they are, and the outreach list is scanned
    # by eye. Country stays in its own column, where it can be filtered on.
    #
    # This is the *record* only. The email still greets "Dear Albrecht & Dill
    # GmbH Team" — the template reads the target's own company_name, which is
    # untouched. Putting an address into a greeting would be unmistakable.
    label = target.company_name
    if target.location:
        label = f"{target.company_name}, {target.location}"
    # Already written to at another address today, on this campaign? Then
    # this is the same company, and it gets the same row.
    twin = db.scalar(
        select(Outreach)
        .join(CampaignTarget, CampaignTarget.outreach_id == Outreach.id)
        .where(
            CampaignTarget.campaign_id == campaign.id,
            Outreach.company_name == label[:200],
        )
        .limit(1)
    )
    if twin is not None:
        existing = [
            a.strip() for a in (twin.email or "").split(",") if a.strip()
        ]
        if target.email and target.email.casefold() not in {
            a.casefold() for a in existing
        }:
            existing.append(target.email)
        twin.email = ", ".join(existing)[:255]
        twin.contact_point = twin.email[:255]

        # The second envelope's own text, if it differs from the first.
        #
        # Both addresses usually receive the identical letter, and storing it
        # twice would double the row for nothing. But they need not be
        # identical — a template reading the contact's name produces different
        # text per mailbox — and "what did we actually say to them" is the
        # question this column exists to answer. So it is compared, and kept
        # only when it says something new, under a heading naming the mailbox
        # it went to.
        written = f"Subject: {subject}\n\n{body}" if subject else body
        if written and written not in (twin.message_sent or ""):
            twin.message_sent = (
                f"{twin.message_sent}\n\n--- to {target.email} ---\n{written}"
                if twin.message_sent
                else written
            )
        # Contacted on the day of the *first* letter: that is when this
        # company heard from us, and a follow-up is counted from it.
        db.commit()
        return twin

    row = Outreach(
        company_name=label[:200],
        contact_person=target.contact_person,
        website=target.website,
        email=target.email,
        country=target.country,
        contact_method=ContactMethod.email,
        contact_point=target.email,
        contacted_on=cm.sending_day(),
        message_sent=f"Subject: {subject}\n\n{body}" if subject else body,
        status=OutreachStatus.waiting_reply,
        next_action="Wait for reply",
        next_follow_up=_in_a_week(),
        # `contacted_on` is a date, so the clock time goes here — a campaign
        # that sends fifty in an afternoon otherwise leaves fifty rows that all
        # claim to have happened at no particular moment.
        notes=(
            f"Sent automatically by campaign “{campaign.name}” "
            f"at {local.strftime('%H:%M')} on {local.strftime('%d %b %Y')} (IST), "
            f"to {target.email}."
        ),
        owner_id=campaign.owner_id,
    )
    db.add(row)
    db.flush()
    return row


def _in_a_week() -> date:
    return cm.sending_day() + timedelta(days=7)


def recover_stuck(db: Session, older_than_minutes: int = 10) -> int:
    """Deal with attempts that started and never finished.

    Called on boot. An attempt still `processing` after the process restarted
    means the send was in flight when everything stopped, and SMTP cannot be
    asked afterwards whether it delivered. Retrying risks a second copy;
    marking it failed invites a retry later. So it becomes `unverified` — out
    of the queue, in front of a person, with the Message-ID recorded so the
    Sent folder can settle it.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
    stuck = db.scalars(
        select(SendAttempt).where(
            SendAttempt.status == AttemptStatus.processing, SendAttempt.started_at < cutoff
        )
    ).all()
    for attempt in stuck:
        attempt.status = AttemptStatus.unverified
        attempt.error = "The app stopped mid-send; delivery unconfirmed."
        attempt.finished_at = datetime.now(timezone.utc)
        target = db.get(CampaignTarget, attempt.target_id)
        if target is not None and target.state == TargetState.processing:
            target.state = TargetState.unverified
            target.last_error = (
                "Delivery unconfirmed — check the Sent folder for "
                f"{attempt.message_id or 'this message'} before retrying."
            )
            cm.record(
                db,
                attempt.campaign_id,
                "unverified",
                f"{target.company_name}: send interrupted, delivery unconfirmed.",
                target.id,
            )
    if stuck:
        db.commit()
        log.warning("Recovered %d interrupted send attempt(s) as unverified", len(stuck))
    return len(stuck)
