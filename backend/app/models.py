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
