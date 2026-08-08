"""Outreach: the record of who we contacted, where, and what came back.

Separate from `contacts` on purpose. A contact is an inbound enquiry moving
through a quoting pipeline; an outreach row is cold prospecting that may never
become one. Keeping them apart means neither form is half-empty.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_current_user
from ..models import OUTREACH_CLOSED, ContactMethod, Outreach, OutreachStatus, User
from ..schemas import (
    DraftMessageRequest,
    DraftMessageResponse,
    OutreachCreate,
    OutreachOut,
    OutreachStats,
    OutreachUpdate,
    ReplyAnalysisResponse,
)
from ..services import ai

router = APIRouter(prefix="/api/outreach", tags=["outreach"])

@router.get("", response_model=list[OutreachOut])
def list_outreach(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    search: str | None = Query(default=None, description="Company, person, website or notes"),
    contact_method: ContactMethod | None = None,
    outreach_status: OutreachStatus | None = Query(default=None, alias="status"),
    due: bool = Query(default=False, description="Only rows whose follow-up is due"),
    limit: int = Query(default=300, ge=1, le=500),
):
    stmt = select(Outreach).options(selectinload(Outreach.owner))

    if search:
        needle = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Outreach.company_name).like(needle),
                func.lower(func.coalesce(Outreach.contact_person, "")).like(needle),
                func.lower(func.coalesce(Outreach.website, "")).like(needle),
                func.lower(func.coalesce(Outreach.email, "")).like(needle),
                func.lower(func.coalesce(Outreach.country, "")).like(needle),
                func.lower(func.coalesce(Outreach.notes, "")).like(needle),
            )
        )
    if contact_method:
        stmt = stmt.where(Outreach.contact_method == contact_method)
    if outreach_status:
        stmt = stmt.where(Outreach.status == outreach_status)
    if due:
        stmt = stmt.where(
            Outreach.next_follow_up.is_not(None),
            Outreach.next_follow_up <= date.today(),
            Outreach.status.not_in(list(OUTREACH_CLOSED)),
        )

    # Anything with a due date first, oldest due date at the top.
    return db.scalars(
        stmt.order_by(Outreach.next_follow_up.is_(None), Outreach.next_follow_up.asc(),
                      Outreach.updated_at.desc()).limit(limit)
    ).all()


@router.get("/stats", response_model=OutreachStats)
def outreach_stats(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    today = date.today()
    counts = dict(
        db.execute(select(Outreach.status, func.count(Outreach.id)).group_by(Outreach.status)).all()
    )
    total = sum(counts.values())
    replied = counts.get(OutreachStatus.replied, 0)

    due_today = (
        db.scalar(
            select(func.count(Outreach.id)).where(
                Outreach.next_follow_up == today,
                Outreach.status.not_in(list(OUTREACH_CLOSED)),
            )
        )
        or 0
    )
    overdue = (
        db.scalar(
            select(func.count(Outreach.id)).where(
                Outreach.next_follow_up < today,
                Outreach.status.not_in(list(OUTREACH_CLOSED)),
            )
        )
        or 0
    )

    method_rows = db.execute(
        select(Outreach.contact_method, func.count(Outreach.id)).group_by(Outreach.contact_method)
    ).all()

    # Of everyone we actually heard back from, one way or the other.
    answered = replied + counts.get(OutreachStatus.not_interested, 0)
    reachable = answered + counts.get(OutreachStatus.no_response, 0) + counts.get(
        OutreachStatus.waiting_reply, 0
    )

    return OutreachStats(
        total=total,
        awaiting_reply=counts.get(OutreachStatus.waiting_reply, 0)
        + counts.get(OutreachStatus.follow_up_sent, 0),
        replied=replied,
        due_today=due_today,
        overdue=overdue,
        no_response=counts.get(OutreachStatus.no_response, 0),
        not_interested=counts.get(OutreachStatus.not_interested, 0),
        reply_rate=round((answered / reachable) * 100, 1) if reachable else 0.0,
        by_method={m.value: c for m, c in method_rows},
    )


@router.get("/{outreach_id}", response_model=OutreachOut)
def get_outreach(
    outreach_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    row = db.scalar(
        select(Outreach).where(Outreach.id == outreach_id).options(selectinload(Outreach.owner))
    )
    if not row:
        raise HTTPException(status_code=404, detail="Outreach record not found")
    return row


@router.post("", response_model=OutreachOut, status_code=status.HTTP_201_CREATED)
def create_outreach(
    payload: OutreachCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = payload.model_dump()
    if not data.get("owner_id"):
        data["owner_id"] = user.id
    if not (data.get("company_name") or "").strip():
        data["company_name"] = "Untitled outreach"

    # Recording a first contact without saying when almost always means today.
    if data.get("message_sent") and not data.get("contacted_on"):
        data["contacted_on"] = date.today()
    # A week is the usual gap before a first chase.
    if data.get("contacted_on") and not data.get("next_follow_up"):
        data["next_follow_up"] = data["contacted_on"] + timedelta(days=7)

    row = Outreach(**data)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{outreach_id}", response_model=OutreachOut)
def update_outreach(
    outreach_id: int,
    payload: OutreachUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    row = db.get(Outreach, outreach_id)
    if not row:
        raise HTTPException(status_code=404, detail="Outreach record not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row


@router.post("/{outreach_id}/follow-up", response_model=OutreachOut)
def log_follow_up(
    outreach_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    days_until_next: int = Query(default=7, ge=1, le=90),
):
    """One tap for 'I chased them again today'."""
    row = db.get(Outreach, outreach_id)
    if not row:
        raise HTTPException(status_code=404, detail="Outreach record not found")
    row.follow_ups_sent = (row.follow_ups_sent or 0) + 1
    row.status = OutreachStatus.follow_up_sent
    row.next_follow_up = date.today() + timedelta(days=days_until_next)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{outreach_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_outreach(
    outreach_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    row = db.get(Outreach, outreach_id)
    if not row:
        raise HTTPException(status_code=404, detail="Outreach record not found")
    db.delete(row)
    db.commit()


# ------------------------------------------------------------------------ ai


@router.post("/draft", response_model=DraftMessageResponse)
def draft_message(payload: DraftMessageRequest, _: User = Depends(get_current_user)):
    """Write a first-contact message, styled for the channel."""
    message, used_ai = ai.draft_outreach(
        payload.company_name,
        payload.contact_person,
        payload.country,
        payload.contact_method.value,
        payload.context,
    )
    return DraftMessageResponse(
        message=message, model=ai.active_model() if used_ai else "template", ai_enabled=used_ai
    )


@router.post("/{outreach_id}/analyse-reply", response_model=ReplyAnalysisResponse)
def analyse_their_reply(
    outreach_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    apply: bool = Query(default=True, description="Save the summary and status onto the record"),
):
    """Read their reply: summarise it, set the status, propose the next move."""
    row = db.get(Outreach, outreach_id)
    if not row:
        raise HTTPException(status_code=404, detail="Outreach record not found")
    if not (row.their_reply or "").strip():
        raise HTTPException(status_code=400, detail="There is no reply recorded to read")

    summary, suggested, action, used_ai = ai.analyse_reply(
        row.company_name, row.their_reply, row.message_sent
    )
    try:
        status_enum = OutreachStatus(suggested)
    except ValueError:
        status_enum = OutreachStatus.replied

    if apply:
        row.reply_summary = summary
        row.status = status_enum
        if not row.replied_on:
            row.replied_on = date.today()
        if not (row.next_action or "").strip():
            row.next_action = action
        db.commit()

    return ReplyAnalysisResponse(
        summary=summary,
        suggested_status=status_enum,
        suggested_action=action,
        model=ai.active_model() if used_ai else "rule-based",
        ai_enabled=used_ai,
    )
