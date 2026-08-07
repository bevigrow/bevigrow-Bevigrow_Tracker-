"""Customer / supplier CRUD, filtering and pipeline board data."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_current_user
from ..models import Activity, Contact, DealStatus, Document, Reminder, TradeType, User
from ..schemas import (
    ActivityOut,
    ContactCreate,
    ContactDetail,
    ContactOut,
    ContactUpdate,
    DocumentOut,
    ReminderOut,
)

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


def _counts(db: Session, contact_ids: list[int]) -> tuple[dict[int, int], dict[int, int]]:
    if not contact_ids:
        return {}, {}
    acts = dict(
        db.execute(
            select(Activity.contact_id, func.count(Activity.id))
            .where(Activity.contact_id.in_(contact_ids))
            .group_by(Activity.contact_id)
        ).all()
    )
    docs = dict(
        db.execute(
            select(Document.contact_id, func.count(Document.id))
            .where(Document.contact_id.in_(contact_ids))
            .group_by(Document.contact_id)
        ).all()
    )
    return acts, docs


def _to_out(contact: Contact, acts: dict[int, int], docs: dict[int, int]) -> ContactOut:
    out = ContactOut.model_validate(contact)
    out.activity_count = acts.get(contact.id, 0)
    out.document_count = docs.get(contact.id, 0)
    return out


@router.get("", response_model=list[ContactOut])
def list_contacts(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    search: str | None = Query(default=None, description="Company, person, country or product"),
    trade_type: TradeType | None = None,
    contact_status: DealStatus | None = Query(default=None, alias="status"),
    country: str | None = None,
    owner_id: int | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Contact).options(selectinload(Contact.owner))

    if search:
        needle = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Contact.company_name).like(needle),
                func.lower(Contact.country).like(needle),
                func.lower(func.coalesce(Contact.contact_person, "")).like(needle),
                func.lower(func.coalesce(Contact.coffee_product, "")).like(needle),
                func.lower(func.coalesce(Contact.email, "")).like(needle),
                func.lower(func.coalesce(Contact.destination_port, "")).like(needle),
                func.lower(func.coalesce(Contact.hs_code, "")).like(needle),
                func.lower(func.coalesce(Contact.rfq_reference, "")).like(needle),
            )
        )
    if trade_type:
        stmt = stmt.where(Contact.trade_type == trade_type)
    if contact_status:
        stmt = stmt.where(Contact.status == contact_status)
    if country:
        stmt = stmt.where(func.lower(Contact.country) == country.strip().lower())
    if owner_id:
        stmt = stmt.where(Contact.owner_id == owner_id)

    stmt = stmt.order_by(Contact.updated_at.desc()).limit(limit).offset(offset)
    contacts = db.scalars(stmt).all()
    acts, docs = _counts(db, [c.id for c in contacts])
    return [_to_out(c, acts, docs) for c in contacts]


@router.get("/countries", response_model=list[str])
def list_countries(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.execute(
        select(Contact.country).distinct().order_by(Contact.country)
    ).scalars().all()
    return [r for r in rows if r]


@router.get("/{contact_id}", response_model=ContactDetail)
def get_contact(
    contact_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    contact = db.scalar(
        select(Contact)
        .where(Contact.id == contact_id)
        .options(
            selectinload(Contact.owner),
            selectinload(Contact.activities).selectinload(Activity.user),
            selectinload(Contact.documents),
            selectinload(Contact.reminders),
        )
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    detail = ContactDetail.model_validate(contact)
    detail.activity_count = len(contact.activities)
    detail.document_count = len(contact.documents)
    detail.activities = [ActivityOut.model_validate(a) for a in contact.activities]
    detail.documents = [
        DocumentOut.model_validate(d).model_copy(
            update={"download_url": f"/api/documents/{d.id}/download"}
        )
        for d in sorted(contact.documents, key=lambda d: d.created_at, reverse=True)
    ]
    detail.reminders = [
        ReminderOut.model_validate(r).model_copy(update={"contact_company": contact.company_name})
        for r in sorted(contact.reminders, key=lambda r: r.due_date)
    ]
    return detail


@router.post("", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
def create_contact(
    payload: ContactCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = payload.model_dump()
    if not data.get("owner_id"):
        data["owner_id"] = user.id
    # A quote with no name is still worth keeping — file it under a
    # placeholder rather than refusing the entry.
    if not (data.get("company_name") or "").strip():
        data["company_name"] = "Untitled quote"
    contact = Contact(**data)
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return _to_out(contact, {}, {})


@router.patch("/{contact_id}", response_model=ContactOut)
def update_contact(
    contact_id: int,
    payload: ContactUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    db.commit()
    db.refresh(contact)
    acts, docs = _counts(db, [contact.id])
    return _to_out(contact, acts, docs)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    # Documents cascade with the contact; their bytes live in the same table,
    # so there is nothing on disk to clean up.
    db.delete(contact)
    db.commit()


@router.get("/{contact_id}/timeline", response_model=list[ActivityOut])
def contact_timeline(
    contact_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    if not db.get(Contact, contact_id):
        raise HTTPException(status_code=404, detail="Contact not found")
    rows = db.scalars(
        select(Activity)
        .where(Activity.contact_id == contact_id)
        .options(selectinload(Activity.user))
        .order_by(Activity.occurred_at.desc())
    ).all()
    return [ActivityOut.model_validate(a) for a in rows]


@router.get("/board/pipeline", response_model=dict[str, list[ContactOut]])
def pipeline_board(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    trade_type: TradeType | None = None,
):
    """Contacts grouped by deal status, for the kanban pipeline view."""
    stmt = select(Contact).options(selectinload(Contact.owner))
    if trade_type:
        stmt = stmt.where(Contact.trade_type == trade_type)
    contacts = db.scalars(stmt.order_by(Contact.updated_at.desc())).all()
    acts, docs = _counts(db, [c.id for c in contacts])

    board: dict[str, list[ContactOut]] = {s.value: [] for s in DealStatus}
    for c in contacts:
        board[c.status.value].append(_to_out(c, acts, docs))
    return board


@router.delete("/{contact_id}/reminders/clear", status_code=status.HTTP_204_NO_CONTENT)
def clear_contact_reminders(
    contact_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    db.query(Reminder).filter(Reminder.contact_id == contact_id).delete()
    db.commit()
