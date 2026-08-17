"""The one country list every picker and suggestion box reads from.

Countries live on two tables — quotes and cold outreach — and neither is the
whole truth. A country that has only ever been prospected is missing from the
quotes list, which is how a freshly typed country can look like it vanished.
This endpoint merges both, so a name typed anywhere is offered everywhere.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Contact, Outreach, User
from ..schemas import CountryOption
from ..services.geo import CountryTally

router = APIRouter(prefix="/api/countries", tags=["countries"])


def tally_countries(db: Session) -> CountryTally:
    """Quote counts, deal value and prospect counts, merged by canonical name."""
    tally = CountryTally()

    for country, count, value in db.execute(
        select(
            Contact.country,
            func.count(Contact.id),
            func.coalesce(func.sum(Contact.estimated_value_usd), 0.0),
        ).group_by(Contact.country)
    ).all():
        tally.add(country, quotes=count, value_usd=float(value or 0))

    for country, count in db.execute(
        select(Outreach.country, func.count(Outreach.id)).group_by(Outreach.country)
    ).all():
        tally.add(country, prospects=count)

    return tally


@router.get("", response_model=list[CountryOption])
def list_countries(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    # Blank countries are dropped: this list is what a picker offers and what a
    # suggestion box completes, and neither can offer "not filled in".
    return [
        CountryOption(name=row.label, quotes=row.quotes, prospects=row.prospects)
        for row in tally_countries(db).rows(include_unknown=False)
    ]
