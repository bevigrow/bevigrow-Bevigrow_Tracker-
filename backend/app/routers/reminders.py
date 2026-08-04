"""Follow-up reminders."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_current_user
from ..models import Contact, Reminder, User
from ..schemas import ReminderCreate, ReminderOut, ReminderUpdate

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


def _to_out(reminder: Reminder) -> ReminderOut:
    out = ReminderOut.model_validate(reminder)
    if reminder.contact is not None:
        out.contact_company = reminder.contact.company_name
    return out


@router.get("", response_model=list[ReminderOut])
def list_reminders(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    include_done: bool = False,
    contact_id: int | None = None,
    due_before: date | None = None,
    limit: int = Query(default=200, ge=1, le=500),
):
    stmt = select(Reminder).options(selectinload(Reminder.contact))
    if not include_done:
        stmt = stmt.where(Reminder.is_done.is_(False))
    if contact_id:
        stmt = stmt.where(Reminder.contact_id == contact_id)
    if due_before:
        stmt = stmt.where(Reminder.due_date <= due_before)
    rows = db.scalars(stmt.order_by(Reminder.due_date.asc()).limit(limit)).all()
    return [_to_out(r) for r in rows]


@router.post("", response_model=ReminderOut, status_code=status.HTTP_201_CREATED)
def create_reminder(
    payload: ReminderCreate, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    contact = db.get(Contact, payload.contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    reminder = Reminder(**payload.model_dump(), source="manual")
    db.add(reminder)
    if contact.next_follow_up is None or payload.due_date < contact.next_follow_up:
        contact.next_follow_up = payload.due_date
    db.commit()
    db.refresh(reminder)
    reminder.contact = contact
    return _to_out(reminder)


@router.patch("/{reminder_id}", response_model=ReminderOut)
def update_reminder(
    reminder_id: int,
    payload: ReminderUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    reminder = db.get(Reminder, reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(reminder, field, value)
    db.commit()
    db.refresh(reminder)
    return _to_out(reminder)


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder(
    reminder_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    reminder = db.get(Reminder, reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    db.delete(reminder)
    db.commit()
