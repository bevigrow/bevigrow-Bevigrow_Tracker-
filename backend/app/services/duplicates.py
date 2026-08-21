"""Has this mailbox already heard from us?

Checked before every single send, against everything the app knows: earlier
rows in this campaign, other campaigns, the outreach log, and the quotes desk.

The unit is the *address*, not the company. That is a deliberate narrowing of
the original rule, because a company with info@ and sales@ is two mailboxes and
blocking the second one means the enquiry sits unread in a mailbox nobody
watches. What must never happen is one mailbox getting the same cold email
twice — that is the thing a recipient notices and remembers.

A company-level match is not a block, but it is worth saying out loud, so it
comes back as context the summary can report.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models import CampaignTarget, Contact, Outreach, TargetState


@dataclass
class Verdict:
    is_duplicate: bool
    reason: str | None = None
    outreach_id: int | None = None
    # Same firm, different mailbox — reported, never blocking.
    company_seen_before: str | None = None


def _fold(value: str | None) -> str:
    return (value or "").strip().casefold()


def check(db: Session, target: CampaignTarget, *, allow_recontact: bool = False) -> Verdict:
    """Decide whether this target may be emailed.

    `allow_recontact` is for follow-up campaigns, which exist precisely to
    write again to somebody already written to. It relaxes the "we have
    spoken before" rules and nothing else: an address that has already been
    sent to *by this same campaign* is still refused, so a follow-up cannot
    double-send within itself.
    """
    address = _fold(target.normalized_email or target.email)
    if not address:
        return Verdict(is_duplicate=False)

    # 1. This address, already written to by an earlier campaign row.
    prior_scope = [
        CampaignTarget.id != target.id,
        func.lower(CampaignTarget.normalized_email) == address,
        CampaignTarget.state == TargetState.sent,
    ]
    if allow_recontact:
        # Within this campaign only — the whole point of a follow-up is that
        # earlier campaigns do not disqualify anybody.
        prior_scope.append(CampaignTarget.campaign_id == target.campaign_id)
    prior = db.scalar(
        select(CampaignTarget)
        .where(*prior_scope)
        .order_by(CampaignTarget.sent_at.desc())
        .limit(1)
    )
    if prior is not None:
        when = prior.sent_at.strftime("%d %b %Y") if prior.sent_at else "earlier"
        return Verdict(
            is_duplicate=True,
            reason=f"Already emailed at this address on {when} (campaign {prior.campaign_id}).",
            outreach_id=prior.outreach_id,
        )

    if allow_recontact:
        # The rules below are all "we have written to them before", which is
        # the premise of a follow-up rather than a reason to refuse it.
        return Verdict(is_duplicate=False)

    # 2. This address, already in the outreach log — including rows logged by
    #    hand long before any campaign existed.
    logged = db.scalar(
        select(Outreach)
        .where(func.lower(func.trim(Outreach.email)) == address)
        .order_by(Outreach.contacted_on.desc().nullslast())
        .limit(1)
    )
    if logged is not None:
        when = logged.contacted_on.strftime("%d %b %Y") if logged.contacted_on else "previously"
        return Verdict(
            is_duplicate=True,
            reason=f"{logged.company_name} was already contacted at this address on {when}.",
            outreach_id=logged.id,
        )

    # 3. This address belongs to a live quote. Sending a cold introduction to
    #    somebody already negotiating a container is worse than not writing.
    quote = db.scalar(
        select(Contact).where(func.lower(func.trim(Contact.email)) == address).limit(1)
    )
    if quote is not None:
        return Verdict(
            is_duplicate=True,
            reason=f"This address is on an existing quote ({quote.company_name}).",
        )

    # Not a duplicate. Is the company nonetheless familiar?
    company = _fold(target.normalized_company)
    seen = None
    if company:
        row = db.scalar(
            select(Outreach)
            .where(
                or_(
                    func.lower(func.trim(Outreach.website)).like(f"%{company}%"),
                    func.lower(func.trim(Outreach.company_name)) == _fold(target.company_name),
                )
            )
            .limit(1)
        )
        if row is not None:
            seen = row.company_name
    return Verdict(is_duplicate=False, company_seen_before=seen)
