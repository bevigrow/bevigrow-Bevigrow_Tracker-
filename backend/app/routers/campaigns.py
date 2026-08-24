"""Campaign endpoints: connect a mailbox, import a file, run the queue.

The Start button calls `/step`. So does the cron, if you set one up. There is
no background loop and no worker process, deliberately — the free instance this
runs on sleeps after fifteen minutes, and a loop inside a sleeping process is a
loop that stops halfway through a campaign without telling anyone. A queue in
the database plus "advance it by N" survives the instance dying mid-send, which
a loop does not.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import (
    Campaign,
    CampaignEvent,
    CampaignStatus,
    CampaignTarget,
    EmailAccount,
    EmailTemplate,
    MailProvider,
    InboundReply,
    Outreach,
    OutreachStatus,
    SendAttempt,
    SendLedger,
    ReplyMatch,
    SendMode,
    TargetState,
    User,
)
from ..schemas import (
    AttemptOut,
    CampaignOut,
    CampaignStatusOut,
    EmailAccountIn,
    EmailAccountOut,
    EventOut,
    ImportReportOut,
    ReplyOut,
    StepResultOut,
    TargetOut,
    TemplateIn,
    TemplateOut,
)
from ..services import assistant
from ..services import campaigns as cm
from ..services import engine, importer, replies as reply_service
from ..services import reports, scheduler, sender, templating

log = logging.getLogger("bevigrow.campaigns.api")

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])
accounts_router = APIRouter(prefix="/api/email-account", tags=["campaigns"])
templates_router = APIRouter(prefix="/api/templates", tags=["campaigns"])
# Their own prefix, not /api/campaigns/replies: that path is one segment
# long and collides with /api/campaigns/{campaign_id}, which is declared
# first and would try to read "replies" as an id.
replies_router = APIRouter(prefix="/api/replies", tags=["replies"])

MAX_IMPORT_MB = 4


def _account_out(account: EmailAccount) -> EmailAccountOut:
    out = EmailAccountOut.model_validate(account)
    out.provider = account.provider.value
    out.has_password = bool(account.smtp_password_enc)
    out.has_api_key = bool(account.api_key_enc)
    out.has_imap_password = bool(account.imap_password_enc)
    return out


def _get(db: Session, campaign_id: int) -> Campaign:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


def _status(db: Session, campaign: Campaign) -> CampaignStatusOut:
    snap = cm.snapshot(db, campaign)
    snap["status"] = snap["status"].value
    snap["mode"] = snap["mode"].value
    return CampaignStatusOut(**snap)


# ------------------------------------------------------------------ mailbox


@accounts_router.get("", response_model=EmailAccountOut | None)
def get_account(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    account = engine.active_account(db)
    return _account_out(account) if account else None


@accounts_router.put("", response_model=EmailAccountOut)
def save_account(
    payload: EmailAccountIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Store the sending mailbox. The password is encrypted before it lands."""
    account = engine.active_account(db) or EmailAccount(from_email=payload.from_email)
    account.from_email = payload.from_email.strip()
    account.from_name = payload.from_name.strip()
    account.smtp_host = payload.smtp_host.strip()
    account.smtp_port = payload.smtp_port
    account.smtp_user = (payload.smtp_user or payload.from_email).strip()
    account.use_starttls = payload.use_starttls
    account.provider = MailProvider(payload.provider)
    account.reply_to = (payload.reply_to or '').strip() or None
    account.daily_limit = min(payload.daily_limit, cm.HARD_DAILY_CAP)
    account.owner_id = user.id
    if payload.password:
        # Gmail shows app passwords in groups of four; people paste them that
        # way and the space is not part of the secret.
        account.smtp_password_enc = sender.encrypt_password(payload.password.replace(" ", ""))
        account.last_verified_at = None
        account.last_error = None
    if payload.api_key:
        account.api_key_enc = sender.encrypt_password(payload.api_key.strip())
        account.last_verified_at = None
        account.last_error = None
    account.imap_host = (payload.imap_host or "imap.gmail.com").strip()
    account.imap_port = payload.imap_port or 993
    account.imap_user = (payload.imap_user or payload.reply_to or payload.from_email).strip()
    account.reply_check_enabled = payload.reply_check_enabled
    if payload.imap_password:
        # Pasted from Google in groups of four; the spaces are not the secret.
        account.imap_password_enc = sender.encrypt_password(
            payload.imap_password.replace(" ", "")
        )
        account.last_reply_error = None
    if account.id is None:
        db.add(account)
    db.commit()
    db.refresh(account)
    return _account_out(account)


@accounts_router.post("/verify", response_model=EmailAccountOut)
def verify_account(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Log in to the mailbox and hang up, so a bad password is found now.

    Rather than on company one of two hundred, which is the alternative.
    """
    account = engine.active_account(db)
    if account is None:
        raise HTTPException(status_code=400, detail="No mailbox is configured.")
    outcome = sender.verify(account)
    from datetime import datetime, timedelta, timezone

    if outcome.ok:
        account.last_verified_at = datetime.now(timezone.utc)
        account.last_error = None
    else:
        account.last_error = outcome.error
    db.commit()
    db.refresh(account)
    if not outcome.ok:
        raise HTTPException(status_code=400, detail=outcome.error)
    return _account_out(account)


# ----------------------------------------------------------------- templates


@templates_router.get("", response_model=list[TemplateOut])
def list_templates(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.scalars(select(EmailTemplate).order_by(EmailTemplate.updated_at.desc())).all()
    out = []
    for row in rows:
        item = TemplateOut.model_validate(row)
        item.placeholders = _placeholders(row)
        out.append(item)
    return out


def _placeholders(template: EmailTemplate) -> list[str]:
    found = {
        next(g for g in m.groups() if g is not None)
        for m in templating.PLACEHOLDER.finditer(f"{template.subject}\n{template.body}")
    }
    return sorted(found)


@templates_router.post("", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: TemplateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    row = EmailTemplate(
        name=payload.name.strip(),
        subject=payload.subject.strip(),
        body=payload.body,
        instructions=payload.instructions,
        owner_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    out = TemplateOut.model_validate(row)
    out.placeholders = _placeholders(row)
    return out


@templates_router.put("/{template_id}", response_model=TemplateOut)
def update_template(
    template_id: int,
    payload: TemplateIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    row = db.get(EmailTemplate, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")
    row.name = payload.name.strip()
    row.subject = payload.subject.strip()
    row.body = payload.body
    row.instructions = payload.instructions
    db.commit()
    db.refresh(row)
    out = TemplateOut.model_validate(row)
    out.placeholders = _placeholders(row)
    return out


# ----------------------------------------------------------------- campaigns


@router.get("", response_model=list[CampaignOut])
def list_campaigns(
    deleted: bool = Query(default=False, description='Show the recycle bin instead'),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Campaign).order_by(Campaign.created_at.desc())
    stmt = stmt.where(
        Campaign.deleted_at.is_not(None) if deleted else Campaign.deleted_at.is_(None)
    )
    rows = db.scalars(stmt).all()
    return [
        CampaignOut.model_validate(r).model_copy(
            update={"status": r.status.value, "mode": r.mode.value}
        )
        for r in rows
    ]


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_companies(
    file: UploadFile = File(...),
    name: str = Form(...),
    template_id: int | None = Form(default=None),
    daily_limit: int = Form(default=50),
    mode: str = Form(default="manual"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Read a company file into a new campaign's queue.

    The file is parsed and thrown away — only rows are kept. There is no
    persistent disk on this plan, so a stored upload would vanish on the next
    deploy and leave the campaign pointing at nothing.
    """
    raw = await file.read()
    if len(raw) > MAX_IMPORT_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Keep the file under {MAX_IMPORT_MB} MB.")

    try:
        report = importer.parse(raw, file.filename or "upload.csv")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not report.rows:
        raise HTTPException(status_code=400, detail="No companies found in that file.")

    campaign = Campaign(
        name=name.strip() or "Untitled campaign",
        template_id=template_id,
        daily_limit=min(daily_limit, cm.HARD_DAILY_CAP),
        mode=SendMode.automatic if mode == "automatic" else SendMode.manual,
        source_filename=file.filename,
        owner_id=user.id,
        status=CampaignStatus.draft,
    )
    db.add(campaign)
    db.flush()

    for row in report.rows:
        db.add(
            CampaignTarget(
                campaign_id=campaign.id,
                position=row.position,
                company_name=row.company_name,
                email=row.email,
                contact_person=row.contact_person,
                website=row.website,
                country=row.country,
                location=row.location,
                linkedin=row.linkedin,
                contact_form=row.contact_form,
                phone=row.phone,
                category=row.category,
                extra=json.dumps(row.extra) if row.extra else None,
                normalized_company=row.normalized_company,
                normalized_email=row.normalized_email,
                domain=row.domain,
                skip_reason=row.skip_reason,
                # Everything starts pending, even rows with no address.
                # Marking them skipped here meant the engine never saw
                # them, so nothing was written to the ledger and they were
                # missing from the report entirely — the one place
                # somebody would look to ask why a company was not
                # written to. The engine skips them on the first step and
                # records the reason.
                state=TargetState.pending,
            )
        )

    cm.record(
        db,
        campaign.id,
        "imported",
        f"{report.addresses} addresses across {report.companies} companies from {file.filename}.",
    )
    db.commit()
    db.refresh(campaign)

    return {
        "campaign": CampaignOut.model_validate(campaign).model_copy(
            update={"status": campaign.status.value, "mode": campaign.mode.value}
        ),
        "report": ImportReportOut(
            file_rows=report.file_rows,
            addresses=report.addresses,
            companies=report.companies,
            multi_address_companies=report.multi_address_companies,
            duplicate_addresses=report.duplicate_addresses,
            without_email=report.without_email,
            invalid_emails=report.invalid_emails,
            possible_duplicates=report.possible_duplicates,
            unmapped_columns=report.unmapped_columns,
            repeated_companies=report.repeated_companies,
            shared_locations=report.shared_locations,
        ),
    }


@router.get("/{campaign_id}", response_model=CampaignStatusOut)
def campaign_status(
    campaign_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    return _status(db, _get(db, campaign_id))


@router.patch("/{campaign_id}", response_model=CampaignStatusOut)
def update_campaign(
    campaign_id: int,
    mode: str | None = Query(default=None, pattern="^(manual|automatic)$"),
    daily_limit: int | None = Query(default=None, ge=1, le=50),
    name: str | None = Query(default=None, min_length=1, max_length=160),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Rename a campaign, or switch between approving each email and sending.

    Changeable mid-campaign on purpose: the point of starting in manual is to
    read the first few and then stop reading them. Drafts already prepared and
    waiting are released back into the queue when the switch is to automatic,
    so they are sent rather than stranded waiting for an approval that is no
    longer part of the flow.
    """
    campaign = _get(db, campaign_id)
    if name and name.strip() and name.strip() != campaign.name:
        # Renaming is allowed at any point, finished campaigns included. The
        # name is a label a person chose to find it by, and the one typed at
        # import — usually the filename — is rarely the one they want six
        # weeks later.
        was, campaign.name = campaign.name, name.strip()
        # The permanent history stores the name it was sent under, so that a
        # deleted campaign still reads sensibly in the report. A rename has to
        # carry through to it: otherwise the report goes on naming a campaign
        # that no longer exists by that name, and the two screens disagree
        # about the same fifty emails.
        db.query(SendLedger).filter(SendLedger.campaign_id == campaign.id).update(
            {SendLedger.campaign_name: campaign.name}, synchronize_session=False
        )
        cm.record(db, campaign.id, "renamed", f'Renamed from "{was}" to "{campaign.name}".')
    if mode:
        campaign.mode = SendMode.automatic if mode == "automatic" else SendMode.manual
        if campaign.mode == SendMode.automatic:
            released = (
                db.query(CampaignTarget)
                .filter(
                    CampaignTarget.campaign_id == campaign.id,
                    CampaignTarget.state == TargetState.awaiting_approval,
                )
                .update({CampaignTarget.state: TargetState.pending}, synchronize_session=False)
            )
            if released:
                cm.record(
                    db,
                    campaign.id,
                    "mode",
                    f"Switched to automatic; {released} waiting draft(s) returned to the queue.",
                )
        else:
            cm.record(db, campaign.id, "mode", "Switched to approving each email first.")
    if daily_limit is not None:
        campaign.daily_limit = min(daily_limit, cm.HARD_DAILY_CAP)
        cm.record(db, campaign.id, "limit", f"Daily limit set to {campaign.daily_limit}.")
    db.commit()
    return _status(db, campaign)


@router.post("/{campaign_id}/start", response_model=CampaignStatusOut)
def start_campaign(
    campaign_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    campaign = _get(db, campaign_id)
    if campaign.template_id is None:
        raise HTTPException(status_code=400, detail="Choose an email template first.")
    # A saved address is not a working mailbox. Checking only that a row exists
    # let a campaign start with no credential stored, so every company would
    # fail one at a time with "no key stored" — a hundred failures for one
    # missing field. The distinct messages matter: "connect a mailbox" and
    # "the mailbox has no password" send you to different places.
    account = engine.active_account(db)
    if account is None:
        raise HTTPException(status_code=400, detail="Connect a sending mailbox first.")
    if not (account.smtp_password_enc or account.api_key_enc):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{account.from_email} has no password or API key saved. "
                "Open Settings and enter one, then press Test connection."
            ),
        )
    try:
        cm.start(db, campaign)
    except cm.TransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # The sender waits longer and longer while there is nothing to do, so it
    # has to be told that there now is. Otherwise pressing Start could sit for
    # minutes before anything happened, which is not what a button means.
    scheduler.nudge()
    return _status(db, campaign)


@router.post("/{campaign_id}/pause", response_model=CampaignStatusOut)
def pause_campaign(
    campaign_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    campaign = _get(db, campaign_id)
    try:
        cm.pause(db, campaign)
    except cm.TransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _status(db, campaign)


@router.post("/{campaign_id}/stop", response_model=CampaignStatusOut)
def stop_campaign(
    campaign_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    campaign = _get(db, campaign_id)
    cm.stop(db, campaign)
    return _status(db, campaign)


@router.post("/{campaign_id}/step", response_model=StepResultOut)
def advance(
    campaign_id: int,
    count: int = Query(default=1, ge=1, le=10),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Move the queue on by up to `count` companies.

    Capped at ten per call so one request cannot hold the only worker for a
    minute. The UI calls this repeatedly while the campaign runs, which also
    means closing the tab stops the sending — no surprise batch continues after
    you have walked away.
    """
    campaign = _get(db, campaign_id)
    account = engine.active_account(db)
    steps = []
    for _i in range(count):
        outcome = engine.step(db, campaign, account=account)
        steps.append(outcome.as_dict)
        if outcome.action == "idle":
            break
    return StepResultOut(steps=steps, status=_status(db, campaign))


@router.get("/{campaign_id}/queue", response_model=list[TargetOut])
def queue(
    campaign_id: int,
    state: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(CampaignTarget).where(CampaignTarget.campaign_id == campaign_id)
    if state:
        stmt = stmt.where(CampaignTarget.state == state)
    rows = db.scalars(stmt.order_by(CampaignTarget.position).limit(limit).offset(offset)).all()
    return [
        TargetOut.model_validate(r).model_copy(update={"state": r.state.value}) for r in rows
    ]


@router.get("/{campaign_id}/attempts", response_model=list[AttemptOut])
def attempts(
    campaign_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Every send that was tried, and what came back — successes and failures."""
    rows = db.scalars(
        select(SendAttempt)
        .where(SendAttempt.campaign_id == campaign_id)
        .order_by(SendAttempt.started_at.desc())
        .limit(limit)
    ).all()
    names = {
        t.id: t.company_name
        for t in db.scalars(
            select(CampaignTarget).where(
                CampaignTarget.id.in_([r.target_id for r in rows] or [0])
            )
        ).all()
    }
    return [
        AttemptOut.model_validate(r).model_copy(
            update={"status": r.status.value, "company_name": names.get(r.target_id)}
        )
        for r in rows
    ]


@router.get("/{campaign_id}/events", response_model=list[EventOut])
def events(
    campaign_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rows = db.scalars(
        select(CampaignEvent)
        .where(CampaignEvent.campaign_id == campaign_id)
        .order_by(CampaignEvent.at.desc())
        .limit(limit)
    ).all()
    return [EventOut.model_validate(r) for r in rows]


@router.post("/{campaign_id}/targets/{target_id}/approve", response_model=StepResultOut)
def approve(
    campaign_id: int,
    target_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Send one draft that was waiting for a person.

    Goes through the same quota reservation and the same crash-safety as an
    automatic send — an approval is a shortcut past the waiting, not past the
    limit.
    """
    campaign = _get(db, campaign_id)
    target = db.get(CampaignTarget, target_id)
    if target is None or target.campaign_id != campaign.id:
        raise HTTPException(status_code=404, detail="Not in this campaign")
    if target.state != TargetState.awaiting_approval:
        raise HTTPException(status_code=400, detail="That draft is not waiting for approval.")
    account = engine.active_account(db)
    if account is None:
        raise HTTPException(status_code=400, detail="Connect a sending mailbox first.")
    outcome = engine.dispatch(db, campaign, target, account)
    return StepResultOut(steps=[outcome.as_dict], status=_status(db, campaign))


@router.post("/{campaign_id}/targets/{target_id}/skip", response_model=StepResultOut)
def skip(
    campaign_id: int,
    target_id: int,
    reason: str = Query(default="Skipped by hand"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    campaign = _get(db, campaign_id)
    target = db.get(CampaignTarget, target_id)
    if target is None or target.campaign_id != campaign.id:
        raise HTTPException(status_code=404, detail="Not in this campaign")
    target.state = TargetState.skipped
    target.skip_reason = reason[:400]
    cm.record(db, campaign.id, "skipped", f"{target.company_name}: {reason}", target.id)
    cm.refresh_completion(db, campaign)
    db.commit()
    return StepResultOut(
        steps=[{"action": "skipped", "message": reason, "company": target.company_name}],
        status=_status(db, campaign),
    )


@router.post("/{campaign_id}/targets/{target_id}/retry", response_model=StepResultOut)
def retry(
    campaign_id: int,
    target_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Put a failed address back in the queue.

    Only a failure. An `unverified` row — where the app stopped mid-send and
    nobody knows whether it arrived — is not retryable here on purpose; check
    the Sent folder and use Skip if it went.
    """
    campaign = _get(db, campaign_id)
    target = db.get(CampaignTarget, target_id)
    if target is None or target.campaign_id != campaign.id:
        raise HTTPException(status_code=404, detail="Not in this campaign")
    if target.state != TargetState.failed:
        raise HTTPException(
            status_code=400,
            detail="Only failed sends can be retried. An unconfirmed send must be checked by hand.",
        )
    target.state = TargetState.pending
    target.last_error = None
    db.commit()
    return StepResultOut(
        steps=[{"action": "queued", "message": "Back in the queue.", "company": target.company_name}],
        status=_status(db, campaign),
    )


@router.post("/chat")
def chat(
    payload: dict,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Run the campaign by typing at it.

    The model only classifies the instruction; every number in the answer is
    read from the database by the same functions the status panel uses. It can
    start, pause and stop, and it can report — it cannot send, because the
    sending is driven a company at a time by the page, which is what makes
    closing the tab a reliable way to stop.
    """
    message = str(payload.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="Say something.")
    campaign_id = payload.get("campaign_id")
    reply = assistant.respond(db, message, int(campaign_id) if campaign_id else None)
    out = {
        "reply": reply.text,
        "action": reply.action,
        "acted": reply.acted,
        "campaign_id": reply.campaign_id,
    }
    if reply.campaign_id:
        campaign = db.get(Campaign, reply.campaign_id)
        if campaign is not None:
            out["status"] = _status(db, campaign).model_dump()
    return out


@router.post("/tick")
def heartbeat(token: str = Query(default=""), steps: int = Query(default=12, ge=1, le=25)):
    """Advance the queue without a login — for an external cron.

    Deliberately unauthenticated-but-secret. A cron cannot hold a session, and
    giving a scheduler a password that never expires is worse than a token that
    does exactly one thing and cannot read anything.

    Two jobs at once: it moves the campaign along, and the request itself keeps
    the instance awake. A host that sleeps an idle process is the whole reason
    a heartbeat exists.
    """
    expected = settings.OUTREACH_TICK_TOKEN.strip()
    if not expected:
        raise HTTPException(
            status_code=404,
            detail="The heartbeat is disabled. Set OUTREACH_TICK_TOKEN to enable it.",
        )
    # Compared in constant time: this endpoint is public, and a token that can
    # be guessed a character at a time is not a secret.
    import hmac

    if not hmac.compare_digest(token.strip(), expected):
        raise HTTPException(status_code=403, detail="Bad token.")
    return scheduler.tick(steps)


@router.get("/system/health")
def outreach_health(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Is the sender actually running, and does it have what it needs?"""
    account = engine.active_account(db)
    active = db.scalars(
        select(Campaign).where(
            Campaign.status.in_([CampaignStatus.running, CampaignStatus.daily_limit])
        )
    ).all()
    quota = cm.quota_state(db)
    return {
        "scheduler_running": scheduler.is_alive(),
        "scheduler_enabled": settings.OUTREACH_SCHEDULER_ENABLED,
        "heartbeat_configured": bool(settings.OUTREACH_TICK_TOKEN.strip()),
        "mailbox_connected": bool(account and account.smtp_password_enc),
        "mailbox_verified": bool(account and account.last_verified_at),
        "campaigns_active": len(active),
        "sent_today": quota["sent"],
        "daily_limit": quota["limit"],
        "pace_seconds": settings.OUTREACH_PACE_SECONDS,
    }


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(
    campaign_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    """Move a campaign to the recycle bin.

    Nothing is destroyed. Delete used to remove the queue, the drafts and the
    send history with no way back, which is a lot to hang on one small icon.
    It is now reversible, and only an explicit purge removes anything.

    The ledger is untouched either way: today's report still knows what went
    out this morning even after the campaign that sent it is binned, which is
    what stops the agent writing to those companies a second time.
    """
    campaign = _get(db, campaign_id)
    if campaign.status in (CampaignStatus.running, CampaignStatus.daily_limit):
        cm.pause(db, campaign, "Paused and moved to the recycle bin.")
    campaign.deleted_at = datetime.now(timezone.utc)
    db.commit()


@router.post("/{campaign_id}/restore", response_model=CampaignStatusOut)
def restore_campaign(
    campaign_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    """Take one back out of the bin, paused, exactly as it was."""
    campaign = _get(db, campaign_id)
    campaign.deleted_at = None
    cm.record(db, campaign.id, "restored", "Restored from the recycle bin.")
    db.commit()
    return _status(db, campaign)


@router.delete("/{campaign_id}/purge", status_code=status.HTTP_204_NO_CONTENT)
def purge_campaign(
    campaign_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    """Destroy a binned campaign for good.

    Its queue, drafts and attempts go. The ledger entries and the outreach
    records do not: those are the history of real emails to real companies, and
    they are what the duplicate check reads. Emptying a bin should tidy the
    workspace, never make the app willing to email somebody twice.
    """
    campaign = _get(db, campaign_id)
    if campaign.deleted_at is None:
        raise HTTPException(
            status_code=400,
            detail="Move it to the recycle bin first — this is the permanent step.",
        )
    db.delete(campaign)
    db.commit()


# ------------------------------------------------------------------ reports


@router.get("/report/daily")
def daily_report(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """What was sent each day, and what was not, and why.

    Read from the ledger rather than from campaigns, so deleting a campaign —
    or emptying the recycle bin — leaves the history standing.
    """
    return {"totals": reports.totals(db), "days": reports.daily(db, days)}


@router.get("/report/countries")
def country_report(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Companies written to per country, counted from the send history.

    The outreach log is the wrong place to count this: it holds a row per
    mailbox when a company is saved that way. This reads the ledger, which
    knows which addresses belonged to one business.
    """
    return reports.sent_by_country(db)


@router.get("/report/trends")
def trend_report(
    months: int = Query(default=12, ge=1, le=36),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Sends and replies by month, country against month, and reply speed."""
    return reports.trends(db, months)


@router.get("/report/duplicates")
def duplicate_report(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Companies sharing a name but differing in address, domain or mailbox."""
    return reports.same_name_different_details(db)


@router.post("/follow-up", status_code=status.HTTP_201_CREATED)
def build_follow_up(
    template_id: int = Query(..., description="The follow-up email to send"),
    days_since: int = Query(default=14, ge=1, le=365),
    limit: int = Query(default=200, ge=1, le=500),
    name: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Queue a second letter to everyone who never answered the first.

    This is where cold outreach actually converts — one email rarely does — and
    it is also the easiest thing to get wrong, so the selection is narrow and
    explicit rather than clever:

      · written to at least `days_since` days ago
      · still waiting on a reply — anybody who answered, said no, or was
        marked no-response is left alone
      · not already in this follow-up

    The campaign it creates is marked as a deliberate re-contact, which is the
    only way past the rule that refuses to write to an address twice. That flag
    cannot be set from an ordinary import.
    """
    cutoff = cm.sending_day() - timedelta(days=days_since)
    candidates = db.scalars(
        select(Outreach)
        .where(
            Outreach.email.is_not(None),
            func.trim(Outreach.email) != "",
            Outreach.status.in_(
                [OutreachStatus.waiting_reply, OutreachStatus.follow_up_sent,
                 OutreachStatus.follow_up_needed]
            ),
            Outreach.contacted_on.is_not(None),
            Outreach.contacted_on <= cutoff,
        )
        .order_by(Outreach.contacted_on.asc())
        .limit(limit)
    ).all()

    if not candidates:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Nobody is waiting on a reply from more than {days_since} days ago. "
                "Try a shorter gap."
            ),
        )

    campaign = Campaign(
        name=name or f"Follow-up · {days_since}+ days · {cm.sending_day():%d %b}",
        template_id=template_id,
        daily_limit=cm.HARD_DAILY_CAP,
        mode=SendMode.manual,
        source_filename="(built from the outreach log)",
        owner_id=user.id,
        status=CampaignStatus.draft,
        allow_recontact=True,
    )
    db.add(campaign)
    db.flush()

    seen: set[str] = set()
    position = 0
    for row in candidates:
        address = (row.email or "").strip().casefold()
        if not address or address in seen:
            continue
        seen.add(address)
        position += 1
        # The company name is stored with its address appended; the template
        # greets by name, so the address is stripped back off here.
        company = (row.company_name or "").split(",")[0].strip() or row.company_name
        db.add(
            CampaignTarget(
                campaign_id=campaign.id,
                position=position,
                company_name=company,
                email=row.email,
                contact_person=row.contact_person,
                website=row.website,
                country=row.country,
                normalized_company=importer.domain_of(row.email, row.website)
                or importer.normalize_company(company),
                normalized_email=importer.normalize_email(row.email),
                domain=importer.domain_of(row.email, row.website),
            )
        )

    cm.record(
        db,
        campaign.id,
        "imported",
        f"{position} companies with no reply after {days_since} days.",
    )
    db.commit()
    db.refresh(campaign)
    return {
        "campaign": CampaignOut.model_validate(campaign).model_copy(
            update={"status": campaign.status.value, "mode": campaign.mode.value}
        ),
        "queued": position,
        "days_since": days_since,
    }


@router.get("/system/imap-reachable")
def imap_reachable(_: User = Depends(get_current_user)):
    """Can this host open a connection to Gmail's IMAP port at all?

    Asked before building anything on it. Outbound SMTP is blocked here, which
    is why campaigns send over HTTPS — and if 993 were blocked too, an inbox
    reader would be dead on arrival no matter how well written. No credentials
    are used: this opens a socket, reads the greeting, and hangs up.
    """
    import socket
    import ssl as ssl_module

    results = {}
    for label, host, port in (
        ("gmail_imap", "imap.gmail.com", 993),
        ("gmail_smtp_587", "smtp.gmail.com", 587),
    ):
        try:
            with socket.create_connection((host, port), timeout=10) as raw:
                if port == 993:
                    ctx = ssl_module.create_default_context()
                    with ctx.wrap_socket(raw, server_hostname=host) as tls:
                        greeting = tls.recv(64).decode("utf-8", "replace").strip()
                else:
                    greeting = raw.recv(64).decode("utf-8", "replace").strip()
            results[label] = {"open": True, "greeting": greeting[:60]}
        except Exception as exc:  # noqa: BLE001 - the failure IS the answer
            results[label] = {"open": False, "error": f"{type(exc).__name__}: {exc}"[:160]}
    return results


# ------------------------------------------------------------------ replies


def _reply_out(db: Session, row: InboundReply) -> ReplyOut:
    """One reply, with the speed worked out against the email it answers."""
    out = ReplyOut.model_validate(row)
    out.match_kind = row.match_kind.value
    out.classification = row.classification.value
    if row.outreach_id:
        source = db.get(Outreach, row.outreach_id)
        if source is not None and source.contacted_on:
            out.sent_at = source.contacted_on
            sent = datetime.combine(source.contacted_on, datetime.min.time(), timezone.utc)
            received = row.received_at
            if received.tzinfo is None:
                received = received.replace(tzinfo=timezone.utc)
            # Negative would mean the reply predates the send, which happens
            # when a date header is wrong; report nothing rather than nonsense.
            hours = (received - sent).total_seconds() / 3600
            out.reply_speed_hours = round(hours, 1) if hours >= 0 else None
    return out


@replies_router.post("/check")
def check_replies(
    days: int = Query(default=14, ge=1, le=90),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Read the mailbox now, rather than waiting for the scheduler."""
    account = engine.active_account(db)
    if account is None or not account.imap_password_enc:
        raise HTTPException(
            status_code=400,
            detail="Add the mailbox App Password in Settings so replies can be read.",
        )
    result = reply_service.sync(db, account, days=days)
    if result.error:
        raise HTTPException(status_code=400, detail=result.error)
    return {
        "checked": result.checked,
        "stored": result.stored,
        "matched": result.matched,
        "unmatched": result.unmatched,
        "skipped": result.skipped,
    }


@accounts_router.post("/verify-inbox", response_model=EmailAccountOut)
def verify_inbox(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Sign in to the mailbox and hang up. Reads nothing, changes nothing."""
    account = engine.active_account(db)
    if account is None:
        raise HTTPException(status_code=400, detail="No mailbox is configured.")
    error = reply_service.check_connection(account)
    account.last_reply_error = error
    db.commit()
    db.refresh(account)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return _account_out(account)


@replies_router.get("", response_model=list[ReplyOut])
def list_replies(
    unmatched: bool = Query(default=False, description="Only the ones needing a decision"),
    limit: int = Query(default=100, ge=1, le=300),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(InboundReply).order_by(InboundReply.received_at.desc()).limit(limit)
    if unmatched:
        stmt = stmt.where(InboundReply.match_kind == ReplyMatch.unmatched)
    return [_reply_out(db, r) for r in db.scalars(stmt).all()]


@replies_router.post("/{reply_id}/match", response_model=ReplyOut)
def match_reply(
    reply_id: int,
    outreach_id: int = Query(..., description="The outreach record it belongs to"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Attach a reply the machine would not guess at.

    Forwarded mail, a colleague answering from their own address, an alias —
    all of them arrive with nothing that proves which company they came from.
    The machine leaves those alone; this is a person saying so.
    """
    reply = db.get(InboundReply, reply_id)
    if reply is None:
        raise HTTPException(status_code=404, detail="Reply not found")
    row = db.get(Outreach, outreach_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Outreach record not found")
    reply.match_kind = ReplyMatch.manual
    reply_service.apply_to_outreach(db, reply, row)
    db.commit()
    db.refresh(reply)
    return _reply_out(db, reply)


@replies_router.post("/{reply_id}/handled", response_model=ReplyOut)
def mark_handled(
    reply_id: int,
    handled: bool = Query(default=True),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Take it off the review list. Nothing is sent, nothing is deleted."""
    reply = db.get(InboundReply, reply_id)
    if reply is None:
        raise HTTPException(status_code=404, detail="Reply not found")
    reply.handled = handled
    db.commit()
    db.refresh(reply)
    return _reply_out(db, reply)
