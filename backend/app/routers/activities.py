"""Daily activity log: create, list, edit, re-summarize."""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_current_user
from ..models import Activity, Channel, Contact, Reminder, User
from ..schemas import ActivityCreate, ActivityOut, ActivityUpdate
from ..services import ai

router = APIRouter(prefix="/api/activities", tags=["activities"])


def _decorate(activity: Activity) -> ActivityOut:
    out = ActivityOut.model_validate(activity)
    if activity.contact is not None:
        out.contact_company = activity.contact.company_name
    return out


@router.get("", response_model=list[ActivityOut])
def list_activities(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    contact_id: int | None = None,
    user_id: int | None = None,
    channel: Channel | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Activity).options(
        selectinload(Activity.user), selectinload(Activity.contact)
    )
    if contact_id:
        stmt = stmt.where(Activity.contact_id == contact_id)
    if user_id:
        stmt = stmt.where(Activity.user_id == user_id)
    if channel:
        stmt = stmt.where(Activity.channel == channel)
    if date_from:
        stmt = stmt.where(
            Activity.occurred_at >= datetime.combine(date_from, datetime.min.time(), timezone.utc)
        )
    if date_to:
        stmt = stmt.where(
            Activity.occurred_at <= datetime.combine(date_to, datetime.max.time(), timezone.utc)
        )

    rows = db.scalars(
        stmt.order_by(Activity.occurred_at.desc()).limit(limit).offset(offset)
    ).all()
    return [_decorate(a) for a in rows]


@router.post("", response_model=ActivityOut, status_code=status.HTTP_201_CREATED)
def create_activity(
    payload: ActivityCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    contact = db.get(Contact, payload.contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    occurred = payload.occurred_at or datetime.now(timezone.utc)

    summary: str | None = None
    if payload.generate_summary:
        raw = payload.discussion
        if payload.customer_reply:
            raw = f"{raw}\nCustomer reply: {payload.customer_reply}"
        summary, _used_ai = ai.summarize_interaction(raw, contact.company_name, contact.country)

    activity = Activity(
        contact_id=contact.id,
        user_id=user.id,
        occurred_at=occurred,
        channel=payload.channel,
        discussion=payload.discussion,
        customer_reply=payload.customer_reply,
        next_follow_up=payload.next_follow_up,
        status_after=payload.status_after,
        ai_summary=summary,
    )
    db.add(activity)

    # Keep the parent contact in sync with the newest interaction.
    contact.last_contacted_at = occurred
    if payload.next_follow_up:
        contact.next_follow_up = payload.next_follow_up
        db.add(
            Reminder(
                contact_id=contact.id,
                due_date=payload.next_follow_up,
                message=f"Follow up with {contact.company_name} after "
                f"{payload.channel.value} on {occurred.date().isoformat()}",
                source="manual",
                priority="medium",
            )
        )
    if payload.status_after:
        contact.status = payload.status_after

    db.commit()
    db.refresh(activity)
    activity.contact = contact
    return _decorate(activity)


@router.patch("/{activity_id}", response_model=ActivityOut)
def update_activity(
    activity_id: int,
    payload: ActivityUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    activity = db.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(activity, field, value)
    if payload.status_after:
        activity.contact.status = payload.status_after
    db.commit()
    db.refresh(activity)
    return _decorate(activity)


@router.post("/{activity_id}/summarize", response_model=ActivityOut)
def resummarize(
    activity_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    """Regenerate the AI summary for an existing activity (Claude Haiku)."""
    activity = db.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    raw = activity.discussion
    if activity.customer_reply:
        raw = f"{raw}\nCustomer reply: {activity.customer_reply}"
    summary, _ = ai.summarize_interaction(
        raw, activity.contact.company_name, activity.contact.country
    )
    activity.ai_summary = summary
    db.commit()
    db.refresh(activity)
    return _decorate(activity)


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(
    activity_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    activity = db.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    db.delete(activity)
    db.commit()
