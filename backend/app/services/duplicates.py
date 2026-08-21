"""Has this mailbox already heard from us?

Checked before every single send, against everything the app knows: earlier
rows in this campaign, other campaigns, the outreach log, and the quotes desk.

The unit is the *address*, not the company: what must never happen is one
mailbox getting the same cold email twice, because that is the thing a
recipient notices and remembers.

A company's mailboxes now travel together — info@ and sales@ at one firm are
addressed on a single message — so a target carries several addresses and each
is checked separately. One refusal refuses the send, since the message would
reach them all on one envelope.

A company-level match is not a block, but it is worth saying out loud, so it
comes back as context the summary can report.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models import CampaignTarget, Contact, Outreach, OutreachStatus, TargetState


@dataclass
class Verdict:
    is_duplicate: bool
    reason: str | None = None
    outreach_id: int | None = None
    # Same firm, different mailbox — reported, never blocking.
    company_seen_before: str | None = None


def _fold(value: str | None) -> str:
    return (value or "").strip().casefold()


def _holds(column, address: str):
    """SQL for "this stored value is, or contains, exactly this address".

    Both `CampaignTarget.normalized_email` and `Outreach.email` may now hold
    several addresses for one company, comma-separated, because the company
    got one message addressed to all of them. Equality would miss those rows
    entirely and let a second cold email through to somebody who already had
    one — so the value is padded with commas at both ends and matched against
    `,address,`. The padding is what makes it exact: a bare LIKE would pair
    `a@x.ae` with `sales-a@x.ae`.
    """
    padded = "," + func.replace(func.lower(func.trim(column)), " ", "") + ","
    return padded.like(f"%,{address},%")


def check(db: Session, target: CampaignTarget, *, allow_recontact: bool = False) -> Verdict:
    """Decide whether this target may be emailed.

    A target can carry several mailboxes at one company — "info@x.ae,
    sales@x.ae" — which go out on a single message. Every one of them is
    checked, and the first that is refused refuses the whole send: if one of
    the two has already had this email, or asked to be left alone, the message
    cannot go, because it would reach them both on one envelope.

    `allow_recontact` is for follow-up campaigns, which exist precisely to
    write again to somebody already written to. It relaxes the "we have
    spoken before" rules and nothing else: an address that has already been
    sent to *by this same campaign* is still refused, so a follow-up cannot
    double-send within itself.
    """
    addresses = [
        _fold(part)
        for part in (target.email or "").replace(";", ",").split(",")
        if _fold(part)
    ]
    if not addresses:
        return Verdict(is_duplicate=False)

    context: str | None = None
    for one in addresses:
        verdict = _check_address(db, target, one, allow_recontact=allow_recontact)
        if verdict.is_duplicate:
            return verdict
        context = context or verdict.company_seen_before
    return Verdict(is_duplicate=False, company_seen_before=context)


def _check_address(
    db: Session, target: CampaignTarget, address: str, *, allow_recontact: bool
) -> Verdict:
    """The rules, applied to one mailbox."""

    # 1. This address, already written to by an earlier campaign row.
    prior_scope = [
        CampaignTarget.id != target.id,
        _holds(CampaignTarget.normalized_email, address),
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

    # Somebody who asked not to be written to again is refused whatever the
    # campaign says. This check sits *above* the follow-up exemption on
    # purpose: a follow-up is allowed to write to people who ignored the first
    # letter, and is never allowed to write to somebody who answered it with
    # "remove me". That distinction is the whole reason the exemption is
    # narrow.
    suppressed = db.scalar(
        select(Outreach)
        .where(
            _holds(Outreach.email, address),
            Outreach.status == OutreachStatus.not_interested,
        )
        .limit(1)
    )
    if suppressed is not None:
        return Verdict(
            is_duplicate=True,
            reason=(
                f"{suppressed.company_name} asked not to be contacted again. "
                "Change the status by hand if that was wrong."
            ),
            outreach_id=suppressed.id,
        )

    if allow_recontact:
        # The rules below are all "we have written to them before", which is
        # the premise of a follow-up rather than a reason to refuse it.
        return Verdict(is_duplicate=False)

    # 2. This address, already in the outreach log — including rows logged by
    #    hand long before any campaign existed.
    logged = db.scalar(
        select(Outreach)
        .where(_holds(Outreach.email, address))
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
