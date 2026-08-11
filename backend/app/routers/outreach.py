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
from ..models import (
    OUTREACH_CLOSED,
    Contact,
    ContactMethod,
    DealStatus,
    Outreach,
    OutreachStatus,
    User,
)
from ..schemas import (
    ContactOut,
    OutreachCreate,
    OutreachGroup,
    OutreachInsights,
    OutreachOut,
    OutreachStats,
    OutreachUpdate,
)

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

    # Alphabetical by company. A prospecting log is something you scan looking
    # for a name you half-remember, so the order has to be predictable — a list
    # sorted by due date reshuffles itself every time a follow-up is logged,
    # and the row you were reading moves. Urgency is already visible per row
    # and available through the "due now" filter, so it does not also need to
    # drive the sort. NULLS LAST keeps unnamed records from heading the list.
    return db.scalars(
        stmt.order_by(
            Outreach.company_name.is_(None),
            func.lower(Outreach.company_name).asc(),
            Outreach.id.asc(),
        ).limit(limit)
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


@router.get("/insights", response_model=OutreachInsights)
def outreach_insights(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    limit: int = Query(default=8, ge=3, le=20, description="Rows per breakdown"),
):
    """Where the prospecting is concentrated, and where it is actually landing.

    Volume alone flatters a country you have written to forty times and never
    heard from, so each row carries its reply count too — the interesting
    reading is the gap between the two.

    Grouped in SQL rather than in Python: the whole table would otherwise cross
    the wire on every page load, and this endpoint is on the critical path for
    the Outreach view.
    """

    def _grouped(column) -> list[OutreachGroup]:
        replied = func.count(Outreach.id).filter(Outreach.status == OutreachStatus.replied)
        awaiting = func.count(Outreach.id).filter(
            Outreach.status.not_in(list(OUTREACH_CLOSED)),
            Outreach.status != OutreachStatus.replied,
        )
        chases = func.coalesce(func.sum(Outreach.follow_ups_sent), 0)
        lead = func.count(Outreach.id).desc()
        rows = db.execute(
            select(column, func.count(Outreach.id), replied, awaiting, chases)
            .where(column.is_not(None), func.trim(column) != "")
            .group_by(column)
            .order_by(lead, func.lower(column).asc())
            .limit(limit)
        ).all()
        return [
            OutreachGroup(
                label=label,
                total=total,
                replied=n_replied,
                awaiting=n_awaiting,
                reply_rate=round(n_replied / total * 100, 1) if total else 0.0,
                follow_ups=int(n_chases or 0),
            )
            for label, total, n_replied, n_awaiting, n_chases in rows
        ]

    distinct = lambda col: db.scalar(  # noqa: E731
        select(func.count(func.distinct(col))).where(col.is_not(None), func.trim(col) != "")
    ) or 0

    return OutreachInsights(
        by_country=_grouped(Outreach.country),
        countries_tracked=distinct(Outreach.country),
        companies_tracked=distinct(Outreach.company_name),
    )


# Declared above /{outreach_id}: FastAPI matches routes in definition order,
# so a literal path registered after a path parameter is never reached —
# /api/outreach/insights would be read as an id and 422 on the int parse.
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


@router.post("/{outreach_id}/convert", response_model=ContactOut, status_code=201)
def convert_to_quote(
    outreach_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Turn a prospect who answered into a quote on the trade desk.

    The bridge between the two workspaces. Cold outreach that lands becomes a
    real enquiry, and re-typing the company, person, country and address by
    hand is both tedious and how details get lost.

    The outreach row is kept and linked, not moved. How a buyer was found —
    which channel, what we said, what they wrote back — is worth having later,
    and it is exactly what would be thrown away by turning the record into a
    quote in place. Converting twice is refused rather than silently making a
    duplicate customer.
    """
    row = db.get(Outreach, outreach_id)
    if not row:
        raise HTTPException(status_code=404, detail="Outreach record not found")
    if row.quote_id and db.get(Contact, row.quote_id):
        raise HTTPException(
            status_code=409,
            detail="This prospect already has a quote. Open it from the trade desk.",
        )

    # Carry across only what an outreach row actually knows. Everything else on
    # a quote — volumes, terms, ports — is answered by the buyer later, and
    # guessing values here would put invented trade terms in front of them.
    quote = Contact(
        company_name=row.company_name or "Untitled quote",
        contact_person=row.contact_person,
        email=row.email,
        country=row.country,
        status=DealStatus.contacted,
        owner_id=row.owner_id or user.id,
        rfq_source=f"Outreach · {row.contact_method.value}",
        notes=_carry_over_notes(row),
    )
    db.add(quote)
    db.flush()  # need the id before linking

    row.quote_id = quote.id
    db.commit()
    db.refresh(quote)
    return quote


def _carry_over_notes(row: Outreach) -> str:
    """Everything the prospect told us, as the quote's opening context."""
    parts: list[str] = [f"Came from outreach via {row.contact_method.value}."]
    if row.contact_point:
        parts.append(f"Found at: {row.contact_point}")
    if row.website:
        parts.append(f"Website: {row.website}")
    if row.contacted_on:
        parts.append(f"First contacted {row.contacted_on:%d %b %Y}.")
    if row.their_reply:
        parts.append(f"\nTheir reply:\n{row.their_reply}")
    if row.notes:
        parts.append(f"\nNotes from outreach:\n{row.notes}")
    return "\n".join(parts)


@router.delete("/{outreach_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_outreach(
    outreach_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    row = db.get(Outreach, outreach_id)
    if not row:
        raise HTTPException(status_code=404, detail="Outreach record not found")
    db.delete(row)
    db.commit()
