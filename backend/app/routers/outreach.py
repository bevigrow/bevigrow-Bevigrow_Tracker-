"""Outreach: the record of who we contacted, where, and what came back.

Separate from `contacts` on purpose. A contact is an inbound enquiry moving
through a quoting pipeline; an outreach row is cold prospecting that may never
become one. Keeping them apart means neither form is half-empty.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_current_user
from ..models import (
    OUTREACH_CLOSED,
    CampaignTarget,
    Contact,
    ContactMethod,
    InboundReply,
    DealStatus,
    Outreach,
    OutreachStatus,
    User,
)
from ..schemas import (
    ContactOut,
    OutreachCreate,
    MergeGroup,
    OutreachGroup,
    OutreachInsights,
    OutreachListOut,
    OutreachOut,
    OutreachStats,
    OutreachUpdate,
)
from ..services.geo import CountryTally, canon

router = APIRouter(prefix="/api/outreach", tags=["outreach"])

@router.get("", response_model=list[OutreachListOut])
def list_outreach(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    search: str | None = Query(default=None, description="Company, person, website or notes"),
    contact_method: ContactMethod | None = None,
    outreach_status: OutreachStatus | None = Query(default=None, alias="status"),
    country: str | None = None,
    due: bool = Query(default=False, description="Only rows whose follow-up is due"),
    limit: int = Query(default=300, ge=1, le=500),
):
    # No owner eager-load: the list does not draw the owner, and shipping the
    # whole nested user on every row was an eighth of the response.
    stmt = select(Outreach)

    ranking = None
    if search and search.strip():
        # Search on words, and rank rather than refuse.
        #
        # This used to match the typed phrase as one contiguous string, so
        # "Spice Star Dubai" found nothing at all: the log holds "Spice Star
        # Foodstuff Trading LLC, Dubai" and the words are not adjacent. The
        # name you half-remember is almost never the name as filed — the
        # location is appended, the legal suffix is there or is not, and the
        # trading word sits in the middle.
        #
        # So the words are matched separately, and a row must account for all
        # of them. Among those, an exact name comes first, then a name
        # starting with what you typed, then the rest.
        #
        # Rows that caught only some of the words are shown *only* when
        # nothing caught them all. Listing them underneath a good match is
        # worse than useless: searching "Spice Star Dubai" would return every
        # company in Dubai, and a screen of near-misses reads as though the
        # search misunderstood you. Falling back to them when there is no
        # proper match is still right, though — one misremembered word should
        # find the row rather than an empty screen.
        phrase = " ".join(search.lower().split())
        name = func.lower(func.coalesce(Outreach.company_name, ""))
        # Everything worth searching, as one string per row.
        haystack = (
            name
            + " " + func.lower(func.coalesce(Outreach.contact_person, ""))
            + " " + func.lower(func.coalesce(Outreach.website, ""))
            + " " + func.lower(func.coalesce(Outreach.email, ""))
            + " " + func.lower(func.coalesce(Outreach.country, ""))
            + " " + func.lower(func.coalesce(Outreach.notes, ""))
        )
        # Single letters are dropped: they match nearly every row and would
        # bury the rows that matched something meaningful.
        words = [w for w in phrase.split() if len(w) > 1] or [phrase]

        # Rows that account for *every* word you typed. These are the answer
        # whenever there are any: searching "Spice Star Dubai" should not put
        # Bombay and Gautam underneath the company you asked for merely
        # because they are also in Dubai.
        full_match = and_(*[haystack.like(f"%{w}%") for w in words])
        # The wider net, used only when the narrow one comes back empty — a
        # misremembered word should still find the row rather than nothing.
        any_match = or_(*[haystack.like(f"%{w}%") for w in words])

        ranking = case(
            (name == phrase, 0),
            (name.like(f"{phrase}%"), 1),
            (and_(*[name.like(f"%{w}%") for w in words]), 2),
            else_=3,
        )
    if contact_method:
        stmt = stmt.where(Outreach.contact_method == contact_method)
    if outreach_status:
        stmt = stmt.where(Outreach.status == outreach_status)
    if country:
        # Case-insensitive, to match every spelling behind one picker option.
        stmt = stmt.where(func.lower(func.trim(Outreach.country)) == canon(country))
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
    order = [
        Outreach.company_name.is_(None),
        func.lower(Outreach.company_name).asc(),
        Outreach.id.asc(),
    ]
    # While searching, closeness of match beats the alphabet: you are looking
    # for one row, not scanning the list.
    if ranking is not None:
        order.insert(0, ranking.asc())

    if ranking is None:
        return db.scalars(stmt.order_by(*order).limit(limit)).all()

    # Narrow first, wide only if narrow found nothing. The second query costs
    # a round trip, and it is only ever paid on a search that would otherwise
    # have shown an empty screen.
    rows = db.scalars(stmt.where(full_match).order_by(*order).limit(limit)).all()
    if rows:
        return rows
    return db.scalars(stmt.where(any_match).order_by(*order).limit(limit)).all()


# --------------------------------------------------------------- combining


# Which status survives when two rows for one company are joined. A reply is
# the most informative thing that can have happened and must never be lost
# behind "waiting"; a refusal outranks silence for the same reason.
_STATUS_RANK = {
    OutreachStatus.replied: 0,
    OutreachStatus.not_interested: 1,
    OutreachStatus.follow_up_sent: 2,
    OutreachStatus.waiting_reply: 3,
    OutreachStatus.no_response: 4,
}


def _mergeable(db: Session) -> list[list[Outreach]]:
    """Groups of rows that are one company written to at several addresses.

    Grouped on the company label, which already carries the location — "Bombay
    Foodstuff Trading Co. LLC, Al Ras, Deira, Dubai" — plus the country. Two
    firms of the same name in the same city would be merged wrongly, which is
    why this is offered as a button and not done silently at startup.
    """
    groups: dict[tuple[str, str], list[Outreach]] = {}
    for row in db.scalars(select(Outreach).order_by(Outreach.id)):
        label = " ".join((row.company_name or "").split()).casefold()
        if not label:
            continue
        key = (label, (row.country or "").strip().casefold())
        groups.setdefault(key, []).append(row)
    return [rows for rows in groups.values() if len(rows) > 1]


@router.get("/mergeable", response_model=list[MergeGroup])
def list_mergeable(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """What combining would do, before anything is combined."""
    return [
        MergeGroup(
            company_name=rows[0].company_name or "",
            country=rows[0].country,
            rows=len(rows),
            emails=[r.email for r in rows if r.email],
            ids=[r.id for r in rows],
        )
        for rows in _mergeable(db)
    ]


@router.post("/merge", response_model=list[MergeGroup])
def merge_duplicates(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Join every company that appears more than once into a single row.

    One row per company, with its addresses on one line, comma-separated —
    which is how new imports have been recorded since they were changed to
    send one email per company. This brings the rows written before that in
    line with them.

    Nothing is thrown away. The addresses are all kept, the earliest contact
    date wins, the most informative status wins, and notes and replies are
    concatenated rather than picked between. Replies already filed against a
    row, and the campaign targets that produced it, are re-pointed at the row
    that survives, so no reply is orphaned by the tidy-up.
    """
    done: list[MergeGroup] = []
    for rows in _mergeable(db):
        keeper, *rest = sorted(
            rows, key=lambda r: (r.contacted_on or date.max, r.id)
        )
        addresses: list[str] = []
        for row in rows:
            for part in (row.email or "").replace(";", ",").split(","):
                one = part.strip()
                if one and one.casefold() not in {a.casefold() for a in addresses}:
                    addresses.append(one)

        notes = [r.notes.strip() for r in rows if r.notes and r.notes.strip()]
        replies = [r.their_reply.strip() for r in rows if r.their_reply and r.their_reply.strip()]
        best = min(rows, key=lambda r: _STATUS_RANK.get(r.status, 9))

        keeper.email = ", ".join(addresses)[:255]
        keeper.contact_point = keeper.email[:255]
        keeper.status = best.status
        keeper.replied_on = min((r.replied_on for r in rows if r.replied_on), default=None)
        keeper.their_reply = "\n\n".join(dict.fromkeys(replies)) or None
        keeper.notes = "\n\n".join(dict.fromkeys(notes)) or None
        # The soonest outstanding follow-up, and none at all once they replied.
        pending = [r.next_follow_up for r in rows if r.next_follow_up]
        keeper.next_follow_up = (
            None if keeper.status == OutreachStatus.replied else (min(pending) if pending else None)
        )

        for row in rest:
            db.query(InboundReply).filter(InboundReply.outreach_id == row.id).update(
                {InboundReply.outreach_id: keeper.id}, synchronize_session=False
            )
            db.query(CampaignTarget).filter(CampaignTarget.outreach_id == row.id).update(
                {CampaignTarget.outreach_id: keeper.id}, synchronize_session=False
            )
            db.delete(row)

        done.append(
            MergeGroup(
                company_name=keeper.company_name or "",
                country=keeper.country,
                rows=len(rows),
                emails=addresses,
                ids=[keeper.id],
            )
        )
    db.commit()
    return done


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
    the Outreach view. What does come back per spelling is the label map — one
    row per way a country has been written, which is a handful of strings.
    """

    def _labels(column) -> dict[str, str]:
        """Canonical key → the spelling most records use.

        The chart's labels are what a click sends to the country filter, so
        they have to be the same strings the picker offers. Deriving them the
        same way as /api/countries is what keeps the two agreeing; a min() over
        the spellings would quietly hand back "JAPAN" where the picker said
        "Japan", and the dropdown would then look empty while filtered.
        """
        tally = CountryTally()
        for value, count in db.execute(
            select(column, func.count(Outreach.id)).group_by(column)
        ).all():
            tally.add(value, prospects=count)
        return {canon(row.label): row.label for row in tally.rows(include_unknown=False)}

    def _grouped(column) -> list[OutreachGroup]:
        replied = func.count(Outreach.id).filter(Outreach.status == OutreachStatus.replied)
        awaiting = func.count(Outreach.id).filter(
            Outreach.status.not_in(list(OUTREACH_CLOSED)),
            Outreach.status != OutreachStatus.replied,
        )
        chases = func.coalesce(func.sum(Outreach.follow_ups_sent), 0)
        lead = func.count(Outreach.id).desc()
        # Grouped on the canonical name, not the raw one: "Norway", "norway"
        # and "Norway " are one country and must not each get a row with a
        # third of the messages.
        key = func.lower(func.trim(column))
        labels = _labels(column)
        rows = db.execute(
            select(key, func.count(Outreach.id), replied, awaiting, chases)
            .where(column.is_not(None), func.trim(column) != "")
            .group_by(key)
            .order_by(lead, key.asc())
            .limit(limit)
        ).all()
        return [
            OutreachGroup(
                label=labels.get(name, name),
                total=total,
                replied=n_replied,
                awaiting=n_awaiting,
                reply_rate=round(n_replied / total * 100, 1) if total else 0.0,
                follow_ups=int(n_chases or 0),
            )
            for name, total, n_replied, n_awaiting, n_chases in rows
        ]

    distinct = lambda col: db.scalar(  # noqa: E731
        select(func.count(func.distinct(func.lower(func.trim(col))))).where(
            col.is_not(None), func.trim(col) != ""
        )
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
