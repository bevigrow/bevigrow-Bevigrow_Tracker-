"""Pydantic request/response models."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import (
    AuthProvider,
    Channel,
    ContactMethod,
    DealStatus,
    DocType,
    OutreachStatus,
    Role,
    TradeType,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- auth / users


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    role: Role = Role.employee


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    name: str | None = None
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserOut(ORMModel):
    id: int
    name: str
    email: EmailStr
    role: Role
    is_active: bool
    created_at: datetime
    auth_provider: AuthProvider = AuthProvider.password
    avatar_url: str | None = None
    last_login: datetime | None = None


class GoogleLoginRequest(BaseModel):
    credential: str = Field(min_length=10, description="Google ID token from GIS")


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    # Deliberately identical whether or not the address exists, so this
    # endpoint cannot be used to enumerate accounts.
    message: str
    email_sent: bool


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=16)
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


class AuthConfigOut(BaseModel):
    """Public, unauthenticated: tells the login page what to render."""

    google_enabled: bool
    google_client_id: str
    self_signup_enabled: bool
    password_reset_enabled: bool
    allowed_email_domains: list[str]


# ------------------------------------------------------------------- contacts


class ContactBase(BaseModel):
    """A quote/RFQ. Nothing here is mandatory except a name to file it under,
    and even that falls back to a placeholder rather than rejecting the entry —
    real marketplace RFQs routinely omit the email, phone, port or country."""

    company_name: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=100)
    contact_person: str | None = None
    # Free text, not EmailStr: buyers paste "-", a name, or several addresses.
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = None
    whatsapp: str | None = None
    trade_type: TradeType = TradeType.export
    coffee_product: str | None = None
    quantity_kg: float | None = None
    quantity_note: str | None = Field(default=None, max_length=200)
    roast_preference: str | None = None
    bean_type: str | None = None
    estimated_value_usd: float | None = None

    # Trade terms as they appear on an RFQ
    hs_code: str | None = Field(default=None, max_length=60)
    shipping_terms: str | None = Field(default=None, max_length=40)
    destination_port: str | None = Field(default=None, max_length=150)
    payment_terms: str | None = Field(default=None, max_length=80)
    origin_preference: str | None = Field(default=None, max_length=200)
    sourcing_from: str | None = Field(default=None, max_length=150)
    rfq_source: str | None = Field(default=None, max_length=150)
    rfq_reference: str | None = Field(default=None, max_length=120)

    status: DealStatus = DealStatus.new_lead
    notes: str | None = None
    next_follow_up: date | None = None


class ContactCreate(ContactBase):
    owner_id: int | None = None


class ContactUpdate(BaseModel):
    company_name: str | None = None
    country: str | None = None
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    trade_type: TradeType | None = None
    coffee_product: str | None = None
    quantity_kg: float | None = None
    quantity_note: str | None = None
    roast_preference: str | None = None
    bean_type: str | None = None
    estimated_value_usd: float | None = None
    hs_code: str | None = None
    shipping_terms: str | None = None
    destination_port: str | None = None
    payment_terms: str | None = None
    origin_preference: str | None = None
    sourcing_from: str | None = None
    rfq_source: str | None = None
    rfq_reference: str | None = None
    status: DealStatus | None = None
    notes: str | None = None
    next_follow_up: date | None = None
    owner_id: int | None = None


class ContactOut(ORMModel):
    id: int
    company_name: str
    country: str | None
    contact_person: str | None
    email: str | None
    phone: str | None
    whatsapp: str | None
    trade_type: TradeType
    coffee_product: str | None
    quantity_kg: float | None
    quantity_note: str | None = None
    roast_preference: str | None
    bean_type: str | None
    estimated_value_usd: float | None
    hs_code: str | None = None
    shipping_terms: str | None = None
    destination_port: str | None = None
    payment_terms: str | None = None
    origin_preference: str | None = None
    sourcing_from: str | None = None
    rfq_source: str | None = None
    rfq_reference: str | None = None
    status: DealStatus
    notes: str | None
    owner_id: int | None
    owner: UserOut | None = None
    last_contacted_at: datetime | None
    next_follow_up: date | None
    created_at: datetime
    updated_at: datetime
    activity_count: int = 0
    document_count: int = 0


class ContactDetail(ContactOut):
    activities: list["ActivityOut"] = []
    documents: list["DocumentOut"] = []
    reminders: list["ReminderOut"] = []


# ------------------------------------------------------------------ activities


class ActivityBase(BaseModel):
    contact_id: int
    channel: Channel = Channel.call
    discussion: str = Field(min_length=1)
    customer_reply: str | None = None
    next_follow_up: date | None = None
    status_after: DealStatus | None = None
    occurred_at: datetime | None = None


class ActivityCreate(ActivityBase):
    generate_summary: bool = True


class ActivityUpdate(BaseModel):
    channel: Channel | None = None
    discussion: str | None = None
    customer_reply: str | None = None
    next_follow_up: date | None = None
    status_after: DealStatus | None = None
    ai_summary: str | None = None


class ActivityOut(ORMModel):
    id: int
    contact_id: int
    user_id: int | None
    occurred_at: datetime
    channel: Channel
    discussion: str
    customer_reply: str | None
    ai_summary: str | None
    next_follow_up: date | None
    status_after: DealStatus | None
    created_at: datetime
    user: UserOut | None = None
    contact_company: str | None = None


# ------------------------------------------------------------------- documents


class DocumentOut(ORMModel):
    id: int
    contact_id: int
    doc_type: DocType
    original_name: str
    content_type: str | None
    size_bytes: int
    note: str | None
    created_at: datetime
    uploaded_by_id: int | None
    download_url: str = ""


# ------------------------------------------------------------------- reminders


class ReminderCreate(BaseModel):
    contact_id: int
    due_date: date
    message: str = Field(min_length=1, max_length=500)
    priority: str = "medium"


class ReminderUpdate(BaseModel):
    due_date: date | None = None
    message: str | None = None
    priority: str | None = None
    is_done: bool | None = None


class ReminderOut(ORMModel):
    id: int
    contact_id: int
    due_date: date
    message: str
    source: str
    priority: str
    is_done: bool
    created_at: datetime
    contact_company: str | None = None


# ------------------------------------------------------------------- dashboard


class KpiSet(BaseModel):
    new_leads: int
    export_orders: int
    import_orders: int
    shipments_in_progress: int
    completed_orders: int
    pending_follow_ups: int
    total_contacts: int
    activities_today: int
    conversion_rate: float
    pipeline_value_usd: float


class CountryStat(BaseModel):
    country: str
    count: int
    value_usd: float


class StatusStat(BaseModel):
    status: DealStatus
    count: int


class TrendPoint(BaseModel):
    label: str
    activities: int
    new_leads: int


class DashboardOut(BaseModel):
    greeting: str
    kpis: KpiSet
    by_country: list[CountryStat]
    by_status: list[StatusStat]
    trend: list[TrendPoint]
    export_vs_import: dict[str, int]
    recent_activities: list[ActivityOut]
    upcoming_follow_ups: list[ReminderOut]


# -------------------------------------------------------------------------- ai


class SummarizeRequest(BaseModel):
    notes: str = Field(min_length=3, max_length=6000)
    company_name: str | None = None
    country: str | None = None


class SummarizeResponse(BaseModel):
    summary: str
    model: str
    ai_enabled: bool


class InsightResponse(BaseModel):
    content: str
    model: str
    generated_at: datetime
    cached: bool
    ai_enabled: bool


class SuggestionItem(BaseModel):
    contact_id: int
    company_name: str
    country: str
    status: DealStatus
    priority: str
    reason: str
    suggested_action: str
    days_since_contact: int | None = None


class SuggestionsResponse(BaseModel):
    suggestions: list[SuggestionItem]
    model: str
    ai_enabled: bool


ContactDetail.model_rebuild()
Token.model_rebuild()


# ------------------------------------------------------------------ outreach


class OutreachBase(BaseModel):
    """Cold-outreach record. Nothing mandatory but a name to file it under."""

    company_name: str | None = Field(default=None, max_length=200)
    contact_person: str | None = None
    website: str | None = Field(default=None, max_length=300)
    email: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=100)

    contact_method: ContactMethod = ContactMethod.email
    contact_point: str | None = Field(default=None, max_length=300)

    contacted_on: date | None = None
    message_sent: str | None = None

    status: OutreachStatus = OutreachStatus.follow_up_needed
    their_reply: str | None = None
    replied_on: date | None = None

    next_action: str | None = None
    next_follow_up: date | None = None
    notes: str | None = None


class OutreachCreate(OutreachBase):
    owner_id: int | None = None


class OutreachUpdate(BaseModel):
    company_name: str | None = None
    contact_person: str | None = None
    website: str | None = None
    email: str | None = None
    country: str | None = None
    contact_method: ContactMethod | None = None
    contact_point: str | None = None
    contacted_on: date | None = None
    message_sent: str | None = None
    status: OutreachStatus | None = None
    their_reply: str | None = None
    replied_on: date | None = None
    next_action: str | None = None
    next_follow_up: date | None = None
    follow_ups_sent: int | None = None
    notes: str | None = None
    owner_id: int | None = None


class OutreachOut(ORMModel):
    id: int
    company_name: str
    contact_person: str | None
    website: str | None
    email: str | None
    country: str | None
    contact_method: ContactMethod
    contact_point: str | None
    contacted_on: date | None
    message_sent: str | None
    status: OutreachStatus
    their_reply: str | None
    reply_summary: str | None
    replied_on: date | None
    next_action: str | None
    next_follow_up: date | None
    follow_ups_sent: int
    notes: str | None
    owner_id: int | None
    owner: UserOut | None = None
    created_at: datetime
    updated_at: datetime


class OutreachStats(BaseModel):
    total: int
    awaiting_reply: int
    replied: int
    due_today: int
    overdue: int
    no_response: int
    not_interested: int
    reply_rate: float
    by_method: dict[str, int]


class DraftMessageRequest(BaseModel):
    company_name: str | None = None
    contact_person: str | None = None
    country: str | None = None
    contact_method: ContactMethod = ContactMethod.email
    # What we know about them, in our own words.
    context: str | None = Field(default=None, max_length=2000)


class DraftMessageResponse(BaseModel):
    message: str
    model: str
    ai_enabled: bool


class ReplyAnalysisResponse(BaseModel):
    summary: str
    suggested_status: OutreachStatus
    suggested_action: str
    model: str
    ai_enabled: bool
