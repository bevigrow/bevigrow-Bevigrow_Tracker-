"""Outreach: the record of who we contacted, where, and what came back.

Separate from `contacts` on purpose. A contact is an inbound enquiry moving
through a quoting pipeline; an outreach row is cold prospecting that may never
become one. Keeping them apart means neither form is half-empty.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, case, func, or_, select, tuple_
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_current_user
from ..models import (
    OUTREACH_CLOSED,
    CampaignTarget,
    MergeSnapshot,
    SendLedger,
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
    MergeHistoryOut,
    MergeUndoOut,
    MergedInto,
    OutreachGroup,
    OutreachInsights,
    OutreachListOut,
    OutreachOut,
    OutreachStats,
    OutreachUpdate,
    PeriodCount,
)
from ..services.geo import CountryTally, canon

# Row-value IN ((a, b), ...) is supported by PostgreSQL and by SQLite from
# 3.15. Both of ours have it; the fallback exists so a stricter backend
# degrades to a wider fetch rather than an error.
_TUPLES_OK = True

# Written out rather than taken from the locale: the app is read in English by
# people whose machines are set to several different ones, and a month that
# changes name depending on whose laptop it is opened on is a bug.
_MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

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
    contacted_from: date | None = Query(
        default=None, description="Only rows contacted on or after this date"
    ),
    contacted_to: date | None = Query(
        default=None, description="Only rows contacted on or before this date"
    ),
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
    # A window on the contact date. Two open-ended bounds rather than a
    # month, because a month is only one of the questions asked of it: "this
    # week", "since the trade fair" and "all of last year" are the same query
    # with different edges, and the picker turns each into a pair of dates.
    #
    # A row with no contact date is not in any window, and is excluded by the
    # comparison rather than by a rule — it has not been contacted, so it
    # cannot have been contacted in March.
    if contacted_from:
        stmt = stmt.where(Outreach.contacted_on >= contacted_from)
    if contacted_to:
        stmt = stmt.where(Outreach.contacted_on <= contacted_to)
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
    # Ask which labels repeat before fetching anything.
    #
    # This used to read every row in the log into memory to group them, on a
    # page that opens constantly. The answer is a GROUP BY, and only the rows
    # belonging to a repeated label ever need loading — on a log where nothing
    # is duplicated, which is the normal state, that is zero rows.
    label = func.lower(func.trim(func.coalesce(Outreach.company_name, "")))
    country = func.lower(func.trim(func.coalesce(Outreach.country, "")))
    repeated = [
        (a, b)
        for a, b in db.execute(
            select(label, country)
            .where(label != "")
            .group_by(label, country)
            .having(func.count(Outreach.id) > 1)
        ).all()
    ]
    if not repeated:
        return []

    groups: dict[tuple[str, str], list[Outreach]] = {}
    wanted = {(a, b) for a, b in repeated}
    for row in db.scalars(
        select(Outreach)
        .where(tuple_(label, country).in_(repeated) if _TUPLES_OK else label.in_([a for a, _ in repeated]))
        .order_by(Outreach.id)
    ):
        key = (
            " ".join((row.company_name or "").split()).casefold(),
            (row.country or "").strip().casefold(),
        )
        if key in wanted:
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
    # Everything this call is about to change, recorded whole before it
    # changes. Written first so that an undo restores the exact prior state
    # rather than a reconstruction of it.
    snapshot: list[dict] = []
    for rows in _mergeable(db):
        keeper, *rest = sorted(
            rows, key=lambda r: (r.contacted_on or date.max, r.id)
        )
        # Taken now, as values, not as a reference: the keeper is about to be
        # written over, and a reference would capture the new state.
        keeper_before = _snapshot_row(keeper)
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

        entry = {
            "keeper_id": keeper.id,
            # The surviving row as it was, so undo does not leave it holding
            # the combined addresses of rows that exist again.
            "keeper_before": keeper_before,
            "absorbed": [],
        }
        for row in rest:
            moved_replies = [
                r.id for r in db.scalars(
                    select(InboundReply).where(InboundReply.outreach_id == row.id)
                )
            ]
            moved_targets = [
                t.id for t in db.scalars(
                    select(CampaignTarget).where(CampaignTarget.outreach_id == row.id)
                )
            ]
            entry["absorbed"].append({
                "row": _snapshot_row(row),
                "replies": moved_replies,
                "targets": moved_targets,
            })
            db.query(InboundReply).filter(InboundReply.outreach_id == row.id).update(
                {InboundReply.outreach_id: keeper.id}, synchronize_session=False
            )
            db.query(CampaignTarget).filter(CampaignTarget.outreach_id == row.id).update(
                {CampaignTarget.outreach_id: keeper.id}, synchronize_session=False
            )
            db.delete(row)
        snapshot.append(entry)

        done.append(
            MergeGroup(
                company_name=keeper.company_name or "",
                country=keeper.country,
                rows=len(rows),
                emails=addresses,
                ids=[keeper.id],
            )
        )
    if snapshot:
        db.add(
            MergeSnapshot(
                companies=len(snapshot),
                rows_removed=sum(len(e["absorbed"]) for e in snapshot),
                payload=json.dumps(snapshot, default=str),
            )
        )
    db.commit()
    return done


# The columns worth putting back. Deliberately explicit: a blanket dump of the
# table would restore ids and timestamps that mean nothing once the row has
# been deleted, and would silently break the day a column is added.
_RESTORE_FIELDS = (
    "company_name", "contact_person", "website", "email", "country",
    "contact_method", "contact_point", "contacted_on", "message_sent",
    "status", "their_reply", "replied_on", "next_action", "next_follow_up",
    "notes", "follow_ups_sent", "owner_id", "quote_id", "contacted_at",
)


def _snapshot_row(row: Outreach) -> dict:
    out: dict = {"id": row.id}
    for field_name in _RESTORE_FIELDS:
        value = getattr(row, field_name, None)
        if hasattr(value, "value"):      # an enum
            value = value.value
        out[field_name] = value
    return out


@router.get("/merge/undoable", response_model=MergeUndoOut | None)
def last_merge(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """The most recent combine, if it can still be reversed."""
    row = db.scalar(
        select(MergeSnapshot)
        .where(MergeSnapshot.undone.is_(False))
        .order_by(MergeSnapshot.id.desc())
        .limit(1)
    )
    if row is None:
        return None
    return MergeUndoOut(
        id=row.id, at=row.at, companies=row.companies, rows_removed=row.rows_removed
    )


@router.post("/merge/undo", response_model=MergeUndoOut)
def undo_merge(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Put back the rows the last combine removed.

    The absorbed rows are recreated with their own addresses and their own
    dates, the surviving row is returned to the values it had, and every reply
    and campaign target that was re-pointed goes back to the row it came from.

    Restored rows get new ids — the old ones are gone and reusing them would
    be a lie about which row this is. Anything that referenced them by id is
    re-pointed explicitly, which is why the ids were recorded.
    """
    snap = db.scalar(
        select(MergeSnapshot)
        .where(MergeSnapshot.undone.is_(False))
        .order_by(MergeSnapshot.id.desc())
        .limit(1)
    )
    if snap is None:
        raise HTTPException(status_code=404, detail="There is no combine to undo.")

    restored = 0
    for entry in json.loads(snap.payload):
        keeper = db.get(Outreach, entry["keeper_id"])
        if keeper is not None:
            for field_name, value in entry["keeper_before"].items():
                if field_name == "id":
                    continue
                if field_name == "status" and value:
                    value = OutreachStatus(value)
                elif field_name == "contact_method" and value:
                    value = ContactMethod(value)
                elif field_name in ("contacted_on", "replied_on", "next_follow_up") and value:
                    value = date.fromisoformat(str(value)[:10])
                setattr(keeper, field_name, value)

        for absorbed in entry["absorbed"]:
            data = dict(absorbed["row"])
            data.pop("id", None)
            if data.get("status"):
                data["status"] = OutreachStatus(data["status"])
            if data.get("contact_method"):
                data["contact_method"] = ContactMethod(data["contact_method"])
            for field_name in ("contacted_on", "replied_on", "next_follow_up"):
                if data.get(field_name):
                    data[field_name] = date.fromisoformat(str(data[field_name])[:10])
            data.pop("contacted_at", None)
            row = Outreach(**data)
            db.add(row)
            db.flush()
            restored += 1
            if absorbed["replies"]:
                db.query(InboundReply).filter(InboundReply.id.in_(absorbed["replies"])).update(
                    {InboundReply.outreach_id: row.id}, synchronize_session=False
                )
            if absorbed["targets"]:
                db.query(CampaignTarget).filter(CampaignTarget.id.in_(absorbed["targets"])).update(
                    {CampaignTarget.outreach_id: row.id}, synchronize_session=False
                )

    snap.undone = True
    db.commit()
    return MergeUndoOut(
        id=snap.id, at=snap.at, companies=snap.companies, rows_removed=restored
    )


@router.get("/merge/splittable", response_model=list[MergeGroup])
def list_splittable(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Rows holding more than one address, which can be given a row each."""
    out: list[MergeGroup] = []
    # Only the rows that hold a separator can hold two addresses, and asking
    # the database for those beats reading the whole log to find them.
    for row in db.scalars(
        select(Outreach)
        .where(or_(Outreach.email.like("%,%"), Outreach.email.like("%;%")))
        .order_by(func.lower(Outreach.company_name))
    ):
        parts = [p.strip() for p in (row.email or "").replace(";", ",").split(",") if p.strip()]
        if len(parts) > 1:
            out.append(
                MergeGroup(
                    company_name=row.company_name or "",
                    country=row.country,
                    rows=len(parts),
                    emails=parts,
                    ids=[row.id],
                )
            )
    return out


@router.post("/merge/split", response_model=list[MergeGroup])
def split_combined(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Give every address on a combined row its own row again.

    The undo above replays a snapshot and is exact. This is the fallback for a
    combine performed before snapshots existed: no record of the original rows
    survives, but nothing was actually lost either — every address is still
    sitting in the combined row, so a row per address can be rebuilt from what
    is there.

    What it cannot recover is the differences between the original rows. Notes
    and replies were concatenated when they were joined, so each rebuilt row
    receives the combined text rather than only its own share, and each gets
    the surviving status and dates. The addresses, the count and the company
    are exactly right; the per-row detail is a copy rather than a restoration,
    and saying so is the point of it being a separate button.
    """
    out: list[MergeGroup] = []
    for row in list(
        db.scalars(
            select(Outreach).where(
                or_(Outreach.email.like("%,%"), Outreach.email.like("%;%"))
            )
        )
    ):
        parts: list[str] = []
        for chunk in (row.email or "").replace(";", ",").split(","):
            one = chunk.strip()
            if one and one.casefold() not in {p.casefold() for p in parts}:
                parts.append(one)
        if len(parts) < 2:
            continue

        # The first address stays on the row that already exists, so anything
        # pointing at it — a reply, a campaign target, a quote — keeps working.
        row.email = parts[0][:255]
        row.contact_point = parts[0][:255]
        for address in parts[1:]:
            db.add(
                Outreach(
                    company_name=row.company_name,
                    contact_person=row.contact_person,
                    website=row.website,
                    email=address[:255],
                    country=row.country,
                    contact_method=row.contact_method,
                    contact_point=address[:255],
                    contacted_on=row.contacted_on,
                    message_sent=row.message_sent,
                    status=row.status,
                    their_reply=row.their_reply,
                    replied_on=row.replied_on,
                    next_action=row.next_action,
                    next_follow_up=row.next_follow_up,
                    notes=row.notes,
                    owner_id=row.owner_id,
                )
            )
        out.append(
            MergeGroup(
                company_name=row.company_name or "",
                country=row.country,
                rows=len(parts),
                emails=parts,
                ids=[row.id],
            )
        )
    db.commit()
    return out


@router.get("/merge/history", response_model=list[MergeHistoryOut])
def merge_history(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Every combine, and exactly which addresses went into which company.

    Kept because combining deletes rows, and "what happened to the other
    Bombay row" is a question worth being able to answer months later without
    reasoning backwards from a comma-separated cell. Entries that were undone
    stay in the list, marked, since an undo is also something that happened.
    """
    out: list[MergeHistoryOut] = []
    for snap in db.scalars(
        select(MergeSnapshot).order_by(MergeSnapshot.id.desc()).limit(limit)
    ):
        details: list[MergedInto] = []
        for entry in json.loads(snap.payload or "[]"):
            before = entry.get("keeper_before") or {}
            keeper = db.get(Outreach, entry.get("keeper_id"))
            absorbed = [
                a["row"].get("email")
                for a in entry.get("absorbed", [])
                if a.get("row", {}).get("email")
            ]
            # The keeper's own address belongs at the front: it was one of the
            # rows that went in, not a separate thing the merge produced.
            if before.get("email"):
                absorbed.insert(0, before["email"])
            details.append(
                MergedInto(
                    company_name=before.get("company_name") or "",
                    country=before.get("country"),
                    absorbed_emails=absorbed,
                    kept_email=keeper.email if keeper is not None else None,
                )
            )
        out.append(
            MergeHistoryOut(
                id=snap.id,
                at=snap.at,
                companies=snap.companies,
                rows_removed=snap.rows_removed,
                undone=snap.undone,
                details=details,
            )
        )
    return out


# ------------------------------------------------------- log reconciliation


def _unlogged(db: Session) -> list[SendLedger]:
    """Emails the ledger says went out that the outreach log does not show.

    The two are written in the same transaction, so they should never
    disagree — but they are separate tables and the ledger is the one that
    cannot be deleted, which makes it the reference. If a send committed and
    the log row did not, this finds it, and the alternative to finding it is
    a company that was emailed and looks untouched.

    Matching on the address rather than the company name: the name gets a
    location appended when it is logged, so comparing names would report
    every row as missing.
    """
    logged: set[str] = set()
    for (raw,) in db.execute(select(Outreach.email).where(Outreach.email.is_not(None))):
        for part in (raw or "").replace(";", ",").split(","):
            if part.strip():
                logged.add(part.strip().casefold())

    missing: list[SendLedger] = []
    for entry in db.scalars(
        select(SendLedger).where(SendLedger.outcome == "sent").order_by(SendLedger.at)
    ):
        address = (entry.email or "").strip().casefold()
        if address and address not in logged:
            missing.append(entry)
    return missing


@router.get("/unlogged", response_model=list[MergeGroup])
def list_unlogged(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """What was emailed but is missing from the log."""
    grouped: dict[str, list[SendLedger]] = {}
    for entry in _unlogged(db):
        label = entry.company_name or entry.email or "?"
        if entry.location:
            label = f"{entry.company_name}, {entry.location}"
        grouped.setdefault(label, []).append(entry)
    return [
        MergeGroup(
            company_name=label,
            country=rows[0].country,
            rows=len(rows),
            emails=[r.email for r in rows if r.email],
            ids=[r.id for r in rows],
        )
        for label, rows in grouped.items()
    ]


@router.post("/relog", response_model=list[MergeGroup])
def relog_from_history(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Rebuild the log rows for emails the history says were sent.

    The ledger keeps the company, the location, the country, the address and
    the day for every message that left, which is everything a log row needs
    except the text of the letter — that lives with the campaign and may be
    gone. The rebuilt row says so rather than inventing one.

    One row per company, as everywhere else. Rows already in the log are left
    exactly as they are; this only fills gaps.
    """
    made: list[MergeGroup] = []
    by_company: dict[str, list[SendLedger]] = {}
    for entry in _unlogged(db):
        label = entry.company_name or entry.email or "?"
        if entry.location:
            label = f"{entry.company_name}, {entry.location}"
        by_company.setdefault(label[:200], []).append(entry)

    for label, entries in by_company.items():
        addresses: list[str] = []
        for entry in entries:
            one = (entry.email or "").strip()
            if one and one.casefold() not in {a.casefold() for a in addresses}:
                addresses.append(one)
        first = min(entries, key=lambda e: e.day)
        joined = ", ".join(addresses)[:255]
        db.add(
            Outreach(
                company_name=label,
                email=joined,
                contact_point=joined,
                country=first.country,
                website=first.website,
                contact_method=ContactMethod.email,
                contacted_on=first.day,
                status=OutreachStatus.waiting_reply,
                next_action="Wait for reply",
                next_follow_up=first.day + timedelta(days=7),
                message_sent=(
                    "Rebuilt from the send history. The letter itself was not "
                    "recorded on this row at the time it was sent."
                ),
                notes=f"Sent by campaign \"{first.campaign_name}\" on {first.day}.",
            )
        )
        made.append(
            MergeGroup(
                company_name=label,
                country=first.country,
                rows=len(entries),
                emails=addresses,
                ids=[],
            )
        )
    db.commit()
    return made


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

    # The months and years that actually hold rows.
    #
    # Grouped by day in SQL and folded up in Python on purpose: date_trunc is
    # PostgreSQL's, strftime is SQLite's, and extract() does not translate
    # cleanly to both. The number of distinct days a campaign ever ran on is
    # small — a few dozen — so one portable query beats two dialect-specific
    # ones and a bug on whichever database is not being tested that week.
    per_day = db.execute(
        select(Outreach.contacted_on, func.count(Outreach.id))
        .where(Outreach.contacted_on.is_not(None))
        .group_by(Outreach.contacted_on)
    ).all()

    by_month: dict[str, int] = {}
    by_year: dict[int, int] = {}
    for day, count in per_day:
        if day is None:
            continue
        by_month[f"{day.year:04d}-{day.month:02d}"] = (
            by_month.get(f"{day.year:04d}-{day.month:02d}", 0) + count
        )
        by_year[day.year] = by_year.get(day.year, 0) + count

    months = [
        PeriodCount(
            value=key,
            label=f"{_MONTH_NAMES[int(key[5:7]) - 1]} {key[:4]}",
            count=count,
            year=int(key[:4]),
        )
        for key, count in sorted(by_month.items(), reverse=True)
    ]
    years = [
        PeriodCount(value=str(y), label=str(y), count=count, year=y)
        for y, count in sorted(by_year.items(), reverse=True)
    ]

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
        months=months,
        years=years,
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
