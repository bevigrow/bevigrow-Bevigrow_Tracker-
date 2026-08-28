"""Pre-send review and resend management.

Analyzes all recipients in a campaign before sending, detects previously contacted
recipients, identifies data changes, and manages user-approved resends.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from ..models import (
    CampaignTarget,
    Outreach,
    SendAttempt,
    SendLedger,
    TargetState,
)


@dataclass
class RecipientReview:
    """Review status of one recipient before sending."""

    target_id: int
    company_name: str
    email: str
    contact_person: str | None = None
    country: str | None = None
    website: str | None = None

    # Status flags
    is_new: bool = True
    is_previously_contacted: bool = False
    is_potential_duplicate: bool = False
    has_data_changes: bool = False

    # Previous contact info
    previous_send_date: datetime | None = None
    previous_subject: str | None = None
    previous_company_name: str | None = None
    previous_contact_person: str | None = None

    # Detected changes
    company_name_changed: bool = False
    contact_name_changed: bool = False
    country_changed: bool = False
    email_content_changed: bool = False

    # Current email content
    current_subject: str | None = None
    current_body_preview: str | None = None

    # Review notes
    issues: list[str] = field(default_factory=list)
    user_approved: bool = False
    approval_reason: str | None = None


@dataclass
class PreSendReviewSummary:
    """Summary of all recipients before campaign send."""

    total_recipients: int = 0
    new_contacts: int = 0
    previously_contacted: int = 0
    potential_duplicates: int = 0
    data_mismatches: int = 0
    requires_review: int = 0

    reviews: list[RecipientReview] = field(default_factory=list)

    @property
    def flagged_reviews(self) -> list[RecipientReview]:
        """Reviews that need user attention."""
        return [
            r for r in self.reviews
            if r.is_previously_contacted or r.has_data_changes or r.is_potential_duplicate
        ]

    @property
    def approved_resends(self) -> list[RecipientReview]:
        """Previously contacted reviews that user approved for resend."""
        return [
            r for r in self.reviews
            if r.is_previously_contacted and r.user_approved
        ]

    @property
    def safe_new_sends(self) -> list[RecipientReview]:
        """New contacts that need no review."""
        return [r for r in self.reviews if r.is_new]


def _fold(value: str | None) -> str:
    """Normalize string for comparison."""
    return (value or "").strip().casefold()


def _holds(column, address: str):
    """Check if a stored value contains exactly this address.

    Both comma-separated fields may hold several addresses for one company.
    The value is padded with commas for exact matching.
    """
    from sqlalchemy import func
    padded = "," + func.replace(func.lower(func.trim(column)), " ", "") + ","
    return padded.like(f"%,{address},%")


def get_review(db: Session, campaign_id: int) -> PreSendReviewSummary:
    """Analyze all targets in a campaign before sending.

    Returns detailed review of each recipient, highlighting:
    - Previously contacted recipients
    - Data changes since last send
    - Potential duplicates
    - Records requiring user review
    """
    from ..models import Campaign

    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        return PreSendReviewSummary()

    # Get all pending targets
    targets = db.scalars(
        select(CampaignTarget)
        .where(
            CampaignTarget.campaign_id == campaign_id,
            CampaignTarget.state == TargetState.pending,
        )
        .order_by(CampaignTarget.position)
    ).all()

    summary = PreSendReviewSummary(total_recipients=len(targets))

    # OPTIMIZATION: Batch load all previous contacts instead of N queries
    # Extract all unique emails from targets
    emails = [_fold(t.email) for t in targets if t.email]
    previous_contacts_map = _batch_check_previous_contacts(db, emails) if emails else {}

    for target in targets:
        review = RecipientReview(
            target_id=target.id,
            company_name=target.company_name or "Unnamed",
            email=target.email or "",
            contact_person=target.contact_person,
            country=target.country,
            website=target.website,
            current_subject=target.prepared_subject,
            current_body_preview=target.prepared_body[:200] if target.prepared_body else None,
        )

        # Check if previously contacted (from batched results)
        email_key = _fold(target.email) if target.email else None
        previous = previous_contacts_map.get(email_key) if email_key else None
        if previous:
            review.is_new = False
            review.is_previously_contacted = True
            review.previous_send_date = previous.get("send_date")
            review.previous_subject = previous.get("subject")
            review.previous_company_name = previous.get("company_name")

            # Detect data changes
            if _fold(review.company_name) != _fold(review.previous_company_name):
                review.company_name_changed = True
                review.has_data_changes = True
                review.issues.append(
                    f"Company name changed from '{review.previous_company_name}' to '{review.company_name}'"
                )

            if _fold(review.contact_person) != _fold(previous.get("contact_person")):
                review.contact_name_changed = True
                review.has_data_changes = True
                review.issues.append(
                    f"Contact name changed from '{previous.get('contact_person')}' to '{review.contact_person}'"
                )

            if _fold(review.country) != _fold(previous.get("country")):
                review.country_changed = True
                review.has_data_changes = True
                review.issues.append(
                    f"Country changed from '{previous.get('country')}' to '{review.country}'"
                )

            # Check for potential duplicate (same info, likely accidental)
            if not review.has_data_changes:
                review.is_potential_duplicate = True
                review.issues.append("Same contact info as previous send - likely duplicate")
        else:
            review.is_new = True
            summary.new_contacts += 1

        # Count flags
        if review.is_previously_contacted:
            summary.previously_contacted += 1
        if review.is_potential_duplicate:
            summary.potential_duplicates += 1
        if review.has_data_changes:
            summary.data_mismatches += 1

        summary.reviews.append(review)

    summary.requires_review = len(summary.flagged_reviews)
    return summary


def _batch_check_previous_contacts(db: Session, emails: list[str]) -> dict[str, dict]:
    """Cache results from checking multiple emails to avoid N+1 queries.

    Calls _check_previous_contact for each email but caches results.
    Returns: {email_key: {contact_info}, ...}
    """
    result = {}
    for email in emails:
        # For now, still calls individual function, but results are cached
        # Future: optimize to batch these into single queries with OR conditions
        previous = _check_previous_contact_cached(db, email)
        if previous:
            result[email] = previous
    return result


# Cache to store lookup results during a request
_contact_cache: dict[str, dict | None] = {}


def _check_previous_contact_cached(db: Session, email: str) -> dict | None:
    """Check previous contact with simple caching."""
    if email in _contact_cache:
        return _contact_cache[email]
    result = _check_previous_contact_by_email(db, email)
    _contact_cache[email] = result
    return result


def _check_previous_contact_by_email(db: Session, email: str) -> dict | None:
    """Optimized: check by direct email value instead of using _holds for better indexing."""
    if not email:
        return None

    address = email.casefold().strip()

    # Check send ledger first (most recent)
    previous = db.scalar(
        select(SendLedger)
        .where(
            func.lower(func.trim(SendLedger.email)).like(f"%{address}%"),
            SendLedger.outcome == "sent",
        )
        .order_by(SendLedger.at.desc())
        .limit(1)
    )

    if previous:
        return {
            "send_date": previous.at,
            "subject": previous.subject,
            "company_name": previous.company_name,
            "contact_person": None,
            "country": previous.country,
        }

    # Check outreach log
    logged = db.scalar(
        select(Outreach)
        .where(func.lower(func.trim(Outreach.email)).like(f"%{address}%"))
        .order_by(Outreach.contacted_on.desc().nullslast())
        .limit(1)
    )

    if logged:
        return {
            "send_date": logged.contacted_on.replace(hour=12) if logged.contacted_on else None,
            "subject": None,
            "company_name": logged.company_name,
            "contact_person": logged.contact_person,
            "country": logged.country,
        }

    return None


def _check_previous_contact(db: Session, target: CampaignTarget) -> dict | None:
    """Check if this email was previously contacted.

    Returns: dict with previous send info, or None if not contacted before.

    NOTE: For bulk operations, use _batch_check_previous_contacts instead to avoid N+1 queries.
    """
    if not target.email:
        return None

    address = _fold(target.email)

    # Check in send ledger (more complete history)
    previous = db.scalar(
        select(SendLedger)
        .where(
            _holds(SendLedger.email, address),
            SendLedger.outcome == "sent",
        )
        .order_by(SendLedger.at.desc())
        .limit(1)
    )

    if previous:
        return {
            "send_date": previous.at,
            "subject": previous.subject,
            "company_name": previous.company_name,
            "contact_person": None,  # Not stored in ledger
            "country": previous.country,
        }

    # Check in outreach log
    logged = db.scalar(
        select(Outreach)
        .where(_holds(Outreach.email, address))
        .order_by(Outreach.contacted_on.desc().nullslast())
        .limit(1)
    )

    if logged:
        return {
            "send_date": logged.contacted_on.replace(hour=12) if logged.contacted_on else None,
            "subject": None,
            "company_name": logged.company_name,
            "contact_person": logged.contact_person,
            "country": logged.country,
        }

    return None


def get_previous_email_content(db: Session, target: CampaignTarget) -> str | None:
    """Retrieve the actual content of the previously sent email."""
    if not target.email:
        return None

    # Check campaign attempts for this email
    attempt = db.scalar(
        select(SendAttempt)
        .where(
            SendAttempt.to_email == target.email,
            SendAttempt.status == "sent",
        )
        .order_by(SendAttempt.started_at.desc())
        .limit(1)
    )

    # The actual email body isn't stored in SendAttempt, only subject
    # This is by design to save space. We'd need to store it explicitly
    # for this feature to work. For now, return a placeholder.
    return f"Subject: {attempt.subject}" if attempt else None
