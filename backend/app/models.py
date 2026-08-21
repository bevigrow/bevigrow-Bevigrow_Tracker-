"""ORM models for the BeviGrow Coffee B2B tracker."""
from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    employee = "employee"


class TradeType(str, enum.Enum):
    export = "export"
    import_ = "import"


class DealStatus(str, enum.Enum):
    new_lead = "new_lead"
    contacted = "contacted"
    quotation_sent = "quotation_sent"
    sample_sent = "sample_sent"
    negotiation = "negotiation"
    order_confirmed = "order_confirmed"
    production = "production"
    shipment_in_progress = "shipment_in_progress"
    delivered = "delivered"
    completed = "completed"
    rejected = "rejected"


class Channel(str, enum.Enum):
    call = "call"
    email = "email"
    whatsapp = "whatsapp"
    meeting = "meeting"
    linkedin = "linkedin"
    other = "other"


class DocType(str, enum.Enum):
    quotation = "quotation"
    invoice = "invoice"
    purchase_order = "purchase_order"
    email_screenshot = "email_screenshot"
    meeting_screenshot = "meeting_screenshot"
    sample_photo = "sample_photo"
    other = "other"


# Statuses that count as won / closed-out for analytics.
CLOSED_WON = {DealStatus.completed, DealStatus.delivered}
OPEN_PIPELINE = {
    DealStatus.new_lead,
    DealStatus.contacted,
    DealStatus.quotation_sent,
    DealStatus.sample_sent,
    DealStatus.negotiation,
}


class AuthProvider(str, enum.Enum):
    password = "password"
    google = "google"


class ContactMethod(str, enum.Enum):
    """How we reached out. Website form matters because many small roasters
    publish neither an email address nor a LinkedIn profile."""

    linkedin = "linkedin"
    email = "email"
    website_form = "website_form"
    instagram = "instagram"
    phone = "phone"
    whatsapp = "whatsapp"
    other = "other"


class OutreachStatus(str, enum.Enum):
    follow_up_needed = "follow_up_needed"
    follow_up_sent = "follow_up_sent"
    waiting_reply = "waiting_reply"
    replied = "replied"
    no_response = "no_response"
    not_interested = "not_interested"


# Statuses where the conversation is over, one way or the other.
OUTREACH_CLOSED = {OutreachStatus.not_interested, OutreachStatus.no_response}


# --------------------------------------------------------------- campaigns
#
# The automated outreach layer. Everything below exists so that the *database*
# decides who is next, whether they are a duplicate, and whether there is quota
# left — never the language model. The AI writes the email and reads the chat;
# it can only ask this schema to act, and this schema can refuse.


class CampaignStatus(str, enum.Enum):
    draft = "draft"              # imported, not started
    running = "running"
    paused = "paused"            # a person stopped it
    daily_limit = "daily_limit"  # quota spent; resumes itself tomorrow
    completed = "completed"      # nothing eligible left
    stopped = "stopped"          # abandoned, kept for the record


class SendMode(str, enum.Enum):
    """Whether a prepared email waits for a human."""

    manual = "manual"
    automatic = "automatic"


class TargetState(str, enum.Enum):
    """Where one company sits in the queue."""

    pending = "pending"
    processing = "processing"
    awaiting_approval = "awaiting_approval"
    sent = "sent"
    failed = "failed"
    duplicate = "duplicate"
    skipped = "skipped"
    cancelled = "cancelled"
    # An attempt that started and never reported back — the process died
    # between "about to send" and "sent". Never retried automatically, because
    # the email may well have gone out. A person decides.
    unverified = "unverified"


# States a target will never leave on its own.
TARGET_TERMINAL = {
    TargetState.sent,
    TargetState.duplicate,
    TargetState.skipped,
    TargetState.cancelled,
}


class AttemptStatus(str, enum.Enum):
    """The outcome of one attempt to send to one company."""

    queued = "queued"
    processing = "processing"
    sent = "sent"
    failed = "failed"
    invalid_email = "invalid_email"
    duplicate_skipped = "duplicate_skipped"
    daily_limit = "daily_limit"
    auth_error = "auth_error"
    provider_error = "provider_error"
    rate_limited = "rate_limited"
    cancelled = "cancelled"
    unverified = "unverified"


class EmailTemplate(Base):
    """One example email, plus the rules for personalising it.

    Stored as a structured configuration rather than left to the model's
    memory: the tone, the placeholders it may fill and the facts it may not
    touch are all data, so the same campaign produces the same kind of email in
    January and in June, whichever model is answering.
    """

    __tablename__ = "email_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # What the AI derived when it read the example, as JSON: the placeholders
    # it found, the tone it observed, the structure it must preserve. Written
    # once per template, then reused for every email — the model re-reading and
    # re-interpreting the template 200 times is how a campaign drifts.
    analysis: Mapped[str | None] = mapped_column(Text)
    # Anything the user said about how to use it ("keep it under 120 words").
    instructions: Mapped[str | None] = mapped_column(Text)

    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="template")


class Campaign(Base):
    """One import of companies, worked through at a controlled pace."""

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus, native_enum=False), default=CampaignStatus.draft, index=True
    )
    mode: Mapped[SendMode] = mapped_column(
        Enum(SendMode, native_enum=False), default=SendMode.manual
    )
    # Per campaign, so a cautious first run can be capped lower than the
    # account's ceiling. The account-wide limit still applies on top.
    daily_limit: Mapped[int] = mapped_column(Integer, default=50)

    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("email_templates.id", ondelete="SET NULL")
    )
    template: Mapped["EmailTemplate | None"] = relationship(back_populates="campaigns")

    source_filename: Mapped[str | None] = mapped_column(String(255))

    # A cache of the queue's own truth, for display. The real position is the
    # first target still `pending` — derived, never stored — because a stored
    # index and a queue can disagree, and when they do the index sends someone
    # twice. This column only answers "what did it just do?".
    last_target_id: Mapped[int | None] = mapped_column(Integer)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    # Set instead of deleting. Delete removes the queue and the drafts along
    # with the campaign, and there is no undo for that — so the button puts it
    # here first, and only an explicit purge destroys anything.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    targets: Mapped[list["CampaignTarget"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    events: Mapped[list["CampaignEvent"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )


class CampaignTarget(Base):
    """One *address* in the queue, and everything that happened to it.

    One row per email address, not per company. A company that lists
    info@ and sales@ becomes two rows sharing a `normalized_company`, and both
    are written to — an enquiry that reaches the inbox nobody reads is a
    company you have not actually contacted. The summary counts them as one
    company and says how many addresses it used, so "68 emails to 61
    companies" reads honestly.

    That makes the duplicate rule address-first:

      same company, same address      → duplicate, skipped
      same company, different address → both sent, grouped in the summary
      different company, same address → skipped; one mailbox, one message

    And it means the daily ceiling counts *emails*, not companies: a day of
    fifty may cover forty-two companies.

    The uploaded columns are kept as given. Nothing here is looked up, guessed
    or enriched: a blank website stays blank, because an invented one is worse
    than an empty cell.
    """

    __tablename__ = "campaign_targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    campaign: Mapped["Campaign"] = relationship(back_populates="targets")

    # Row order from the uploaded file. The queue is worked in this order, so
    # "resume from where it stopped" means "the lowest position still pending".
    position: Mapped[int] = mapped_column(Integer, index=True)

    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_person: Mapped[str | None] = mapped_column(String(150))
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    website: Mapped[str | None] = mapped_column(String(300))
    country: Mapped[str | None] = mapped_column(String(100))
    location: Mapped[str | None] = mapped_column(String(200))
    linkedin: Mapped[str | None] = mapped_column(String(300))
    contact_form: Mapped[str | None] = mapped_column(String(300))
    phone: Mapped[str | None] = mapped_column(String(60))
    category: Mapped[str | None] = mapped_column(String(150))
    # Columns the file had that this table has no home for, as JSON. Kept
    # because the template may reference them and discarding a column the user
    # deliberately supplied is a silent loss.
    extra: Mapped[str | None] = mapped_column(Text)

    # Comparison keys, computed once at import so duplicate checks are an
    # indexed lookup rather than a scan with string munging per row.
    normalized_company: Mapped[str | None] = mapped_column(String(200), index=True)
    domain: Mapped[str | None] = mapped_column(String(200), index=True)
    normalized_email: Mapped[str | None] = mapped_column(String(255), index=True)

    state: Mapped[TargetState] = mapped_column(
        Enum(TargetState, native_enum=False), default=TargetState.pending, index=True
    )
    # Why it is not going to be emailed, in words a person can read back.
    skip_reason: Mapped[str | None] = mapped_column(String(400))
    # The outreach row or earlier target this duplicates, when that is why.
    duplicate_of_outreach_id: Mapped[int | None] = mapped_column(Integer)

    # The personalised draft. Written before sending, kept afterwards, and
    # copied verbatim into the outreach record once it has actually gone.
    prepared_subject: Mapped[str | None] = mapped_column(String(300))
    prepared_body: Mapped[str | None] = mapped_column(Text)
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The Log Outreach row this became. The link is what stops a re-import from
    # quietly writing a second record for the same conversation.
    outreach_id: Mapped[int | None] = mapped_column(
        ForeignKey("outreach.id", ondelete="SET NULL")
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class SendAttempt(Base):
    """One try at sending one email — the audit trail, successes and failures.

    Written *before* the send and updated after, so a crash mid-send leaves a
    row saying "we were about to email this address" rather than no trace at
    all. That row is what stops the queue from cheerfully sending it again.
    """

    __tablename__ = "send_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    target_id: Mapped[int] = mapped_column(
        ForeignKey("campaign_targets.id", ondelete="CASCADE"), index=True
    )
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)

    to_email: Mapped[str | None] = mapped_column(String(255))
    subject: Mapped[str | None] = mapped_column(String(300))

    status: Mapped[AttemptStatus] = mapped_column(
        Enum(AttemptStatus, native_enum=False), default=AttemptStatus.queued, index=True
    )
    error: Mapped[str | None] = mapped_column(String(600))

    # The Message-ID this app generated and handed to the mail server. It is
    # the only handle SMTP gives us on a specific message, so it is how a
    # "did this actually go?" question gets answered later.
    message_id: Mapped[str | None] = mapped_column(String(255), index=True)
    provider_response: Mapped[str | None] = mapped_column(String(400))

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DailyQuota(Base):
    """How many sends one day was allowed, and how many it used.

    A row per day rather than a counter that resets: yesterday's number has to
    survive into next month's reporting, and a single mutable counter cannot
    say what happened on the 14th. The count is incremented in the same
    transaction that records a successful send, under a row lock, so two
    workers cannot both read 49 and both send.
    """

    __tablename__ = "daily_quotas"

    id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    # Which mailbox the quota belongs to. Gmail counts per account, not per
    # campaign, so the ceiling has to be shared across campaigns.
    account_id: Mapped[int] = mapped_column(Integer, default=0, index=True)

    limit_value: Mapped[int] = mapped_column(Integer, default=50)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class CampaignEvent(Base):
    """Operational notes: what the agent did, and why, in order.

    This is the "AI memory" the assistant reads back to you — except it is a
    table, so it survives a restart, cannot hallucinate an event that did not
    happen, and can be shown to someone who was not in the conversation.
    """

    __tablename__ = "campaign_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    campaign: Mapped["Campaign"] = relationship(back_populates="events")
    target_id: Mapped[int | None] = mapped_column(Integer)

    kind: Mapped[str] = mapped_column(String(40), index=True)
    message: Mapped[str] = mapped_column(String(600), nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class MailProvider(str, enum.Enum):
    """How the mail physically leaves the building.

    SMTP is the obvious one and the best one when it is available: the message
    goes out of the operator's own mailbox, lands in their Sent folder, and
    replies come back to it with no forwarding tricks.

    It is also unavailable on this application's hosting plan. Free instances
    there stopped allowing outbound traffic to ports 25, 465 and 587 in
    September 2025, so a connection to smtp.gmail.com fails with "network is
    unreachable" before any password is checked. The HTTP providers below send
    over port 443, which is not blocked, and exist for that reason.
    """

    smtp = "smtp"
    resend = "resend"
    brevo = "brevo"


class SendLedger(Base):
    """Every decision the agent ever made, kept forever.

    Deliberately outside the campaign it came from. Campaign rows cascade —
    delete a campaign and its queue, drafts and attempts go with it, which is
    right, because a deleted test run should not clutter the app. What is *not*
    right is that the history goes too: delete this morning's test and the
    agent no longer knows it wrote to anyone this morning, so it will happily
    do it again and today's figures reset to zero.

    So this table holds no foreign key to campaigns and copies the campaign's
    name into itself. Nothing removes a row here except a person explicitly
    purging it. It is the answer to "what did we send, and when, and why was
    that one skipped" long after the campaign is gone.
    """

    __tablename__ = "send_ledger"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    # The operator's day, not UTC's — so a report headed "20 August" holds what
    # a person in Kerala did on the twentieth.
    day: Mapped[date] = mapped_column(Date, index=True)

    # Plain columns, not references. A reference would either block the delete
    # or be nulled by it, and both lose the answer.
    campaign_id: Mapped[int | None] = mapped_column(Integer, index=True)
    campaign_name: Mapped[str] = mapped_column(String(160), default="")

    company_name: Mapped[str] = mapped_column(String(200), default="")
    normalized_company: Mapped[str | None] = mapped_column(String(200), index=True)
    location: Mapped[str | None] = mapped_column(String(200))
    country: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    domain: Mapped[str | None] = mapped_column(String(200), index=True)
    website: Mapped[str | None] = mapped_column(String(300))

    # sent | failed | duplicate | skipped | unverified
    outcome: Mapped[str] = mapped_column(String(20), index=True)
    # Why, in the words a person can read back: "already contacted on 18 Aug".
    reason: Mapped[str | None] = mapped_column(String(400))
    subject: Mapped[str | None] = mapped_column(String(300))
    message_id: Mapped[str | None] = mapped_column(String(255))


class EmailAccount(Base):
    """The mailbox campaigns send from.

    The password or API key is encrypted at rest and never leaves the server —
    no API response, no log line, no error message includes it. What the UI may
    show is the address, the provider, and whether the last connection worked.
    """

    __tablename__ = "email_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(120), default="")
    from_name: Mapped[str] = mapped_column(String(120), default="")
    from_email: Mapped[str] = mapped_column(String(255), nullable=False)

    provider: Mapped[MailProvider] = mapped_column(
        Enum(MailProvider, native_enum=False), default=MailProvider.smtp
    )
    # For the HTTP providers. Encrypted exactly like the SMTP password.
    api_key_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    # Where replies should go when the From address is not the mailbox being
    # watched — sending as kothai@bevigrow.com through a provider while
    # replies land in the Gmail inbox that is actually read.
    reply_to: Mapped[str | None] = mapped_column(String(255))

    smtp_host: Mapped[str] = mapped_column(String(200), default="smtp.gmail.com")
    smtp_port: Mapped[int] = mapped_column(Integer, default=587)
    smtp_user: Mapped[str] = mapped_column(String(255), default="")
    # Fernet ciphertext, keyed from JWT_SECRET. Never a plain password.
    smtp_password_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    use_starttls: Mapped[bool] = mapped_column(Boolean, default=True)

    # Gmail's own ceiling is far higher than this; the point of the number is
    # to look like a person, not to max out an allowance.
    daily_limit: Mapped[int] = mapped_column(Integer, default=50)
    is_default: Mapped[bool] = mapped_column(Boolean, default=True)

    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(400))

    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # Empty for Google-only accounts, which have no password to hash.
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    role: Mapped[Role] = mapped_column(Enum(Role, native_enum=False), default=Role.employee)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # --- sign-in method
    auth_provider: Mapped[AuthProvider] = mapped_column(
        Enum(AuthProvider, native_enum=False), default=AuthProvider.password
    )
    # Google's stable subject id. Never the email — users can change that.
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- password reset
    # Only the hash is stored, so a database leak cannot be replayed as a
    # valid reset link.
    reset_token_hash: Mapped[str | None] = mapped_column(String(128), index=True)
    reset_token_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    contacts: Mapped[list["Contact"]] = relationship(back_populates="owner")
    activities: Mapped[list["Activity"]] = relationship(back_populates="user")


class Contact(Base):
    """A coffee customer (export) or supplier (import)."""

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Only the company name is required, and even that is filled with a
    # placeholder rather than rejected. Real RFQs routinely omit an email, a
    # phone number, or a port — refusing them would mean losing the enquiry.
    company_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    country: Mapped[str | None] = mapped_column(String(100), index=True)
    contact_person: Mapped[str | None] = mapped_column(String(150))
    # Plain strings, not validated emails: buyers often paste "-" or a name.
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(60))
    whatsapp: Mapped[str | None] = mapped_column(String(60))

    trade_type: Mapped[TradeType] = mapped_column(
        Enum(TradeType, native_enum=False), default=TradeType.export, index=True
    )
    coffee_product: Mapped[str | None] = mapped_column(String(150))
    quantity_kg: Mapped[float | None] = mapped_column(Float)
    # The requirement as the buyer wrote it: "600 Kg each item",
    # "700kg to 1 ton per month", "1 Twenty-Foot Container".
    quantity_note: Mapped[str | None] = mapped_column(String(200))
    roast_preference: Mapped[str | None] = mapped_column(String(100))
    bean_type: Mapped[str | None] = mapped_column(String(100))
    estimated_value_usd: Mapped[float | None] = mapped_column(Float)

    # --- trade terms, as they appear on a marketplace RFQ
    hs_code: Mapped[str | None] = mapped_column(String(60))
    shipping_terms: Mapped[str | None] = mapped_column(String(40))
    destination_port: Mapped[str | None] = mapped_column(String(150))
    payment_terms: Mapped[str | None] = mapped_column(String(80))
    origin_preference: Mapped[str | None] = mapped_column(String(200))
    sourcing_from: Mapped[str | None] = mapped_column(String(150))
    rfq_source: Mapped[str | None] = mapped_column(String(150))
    rfq_reference: Mapped[str | None] = mapped_column(String(120))

    status: Mapped[DealStatus] = mapped_column(
        Enum(DealStatus, native_enum=False), default=DealStatus.new_lead, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)

    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    owner: Mapped["User | None"] = relationship(back_populates="contacts")

    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_follow_up: Mapped[date | None] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    activities: Mapped[list["Activity"]] = relationship(
        back_populates="contact", cascade="all, delete-orphan", order_by="Activity.occurred_at.desc()"
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="contact", cascade="all, delete-orphan"
    )
    reminders: Mapped[list["Reminder"]] = relationship(
        back_populates="contact", cascade="all, delete-orphan"
    )


class Activity(Base):
    """One logged interaction with a customer or supplier."""

    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    channel: Mapped[Channel] = mapped_column(Enum(Channel, native_enum=False), default=Channel.call)
    discussion: Mapped[str] = mapped_column(Text, nullable=False)
    customer_reply: Mapped[str | None] = mapped_column(Text)
    ai_summary: Mapped[str | None] = mapped_column(Text)
    next_follow_up: Mapped[date | None] = mapped_column(Date)
    status_after: Mapped[DealStatus | None] = mapped_column(Enum(DealStatus, native_enum=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    contact: Mapped["Contact"] = relationship(back_populates="activities")
    user: Mapped["User | None"] = relationship(back_populates="activities")


class Document(Base):
    """Uploaded proof: quotation, invoice, PO, screenshot, sample photo.

    The bytes live in this table, not on the container filesystem. Render's
    free instances have no persistent disk — the filesystem is rebuilt on every
    deploy, so files stored there disappear silently and the record is left
    pointing at nothing. The database survives deploys, so uploads do too.
    """

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), index=True
    )
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    doc_type: Mapped[DocType] = mapped_column(Enum(DocType, native_enum=False), default=DocType.other)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Retained for rows written before files moved into the database.
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    content: Mapped[bytes | None] = mapped_column(LargeBinary)
    content_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(String(400))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    contact: Mapped["Contact"] = relationship(back_populates="documents")


class Reminder(Base):
    """A scheduled or AI-suggested follow-up."""

    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), index=True
    )
    due_date: Mapped[date] = mapped_column(Date, index=True)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual | ai
    priority: Mapped[str] = mapped_column(String(20), default="medium")  # low|medium|high
    is_done: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    contact: Mapped["Contact"] = relationship(back_populates="reminders")


class AIInsight(Base):
    """Cached AI-generated narrative so the dashboard doesn't re-bill on refresh."""

    __tablename__ = "ai_insights"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(50), index=True)  # dashboard | weekly | follow_ups
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(60), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class Outreach(Base):
    """One company we have reached out to, and everything that followed.

    Deliberately separate from `Contact`. A Contact is an inbound enquiry that
    already wants coffee and moves through a quoting pipeline. An Outreach row
    is cold prospecting: we found a roaster, we messaged them somewhere, and we
    are waiting to hear back. Forcing both through one table would mean every
    quote carried empty outreach fields and every prospect carried empty trade
    terms.

    The whole conversation lives on the row rather than in a child table —
    outbound prospecting is a handful of touches, not a long history, and one
    row per company keeps the list scannable.
    """

    __tablename__ = "outreach"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Nothing is mandatory except a name to file it under.
    company_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    contact_person: Mapped[str | None] = mapped_column(String(150))
    website: Mapped[str | None] = mapped_column(String(300))
    email: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(100), index=True)

    contact_method: Mapped[ContactMethod] = mapped_column(
        Enum(ContactMethod, native_enum=False), default=ContactMethod.email, index=True
    )
    # Where exactly, when the method alone is not enough: a LinkedIn URL, the
    # contact-form page, the inbox the message went to.
    contact_point: Mapped[str | None] = mapped_column(String(300))

    contacted_on: Mapped[date | None] = mapped_column(Date, index=True)
    message_sent: Mapped[str | None] = mapped_column(Text)

    status: Mapped[OutreachStatus] = mapped_column(
        Enum(OutreachStatus, native_enum=False),
        default=OutreachStatus.follow_up_needed,
        index=True,
    )
    their_reply: Mapped[str | None] = mapped_column(Text)
    replied_on: Mapped[date | None] = mapped_column(Date)

    next_action: Mapped[str | None] = mapped_column(Text)
    next_follow_up: Mapped[date | None] = mapped_column(Date, index=True)
    follow_ups_sent: Mapped[int] = mapped_column(Integer, default=0)

    # The digital memory: anything worth remembering next time we talk.
    notes: Mapped[str | None] = mapped_column(Text)

    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    owner: Mapped["User | None"] = relationship()

    # Set once this prospect turns into a real enquiry. The outreach row is
    # kept rather than moved: how a buyer was found is worth remembering, and
    # deleting it would lose the reply that started the conversation.
    # SET NULL, not CASCADE — deleting the quote must not erase the history.
    quote_id: Mapped[int | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
