export type Role = 'admin' | 'manager' | 'employee'
export type TradeType = 'export' | 'import'
export type Channel = 'call' | 'email' | 'whatsapp' | 'meeting' | 'linkedin' | 'other'
export type DocType =
  | 'quotation'
  | 'invoice'
  | 'purchase_order'
  | 'email_screenshot'
  | 'meeting_screenshot'
  | 'sample_photo'
  | 'other'

export type DealStatus =
  | 'new_lead'
  | 'contacted'
  | 'quotation_sent'
  | 'sample_sent'
  | 'negotiation'
  | 'order_confirmed'
  | 'production'
  | 'shipment_in_progress'
  | 'delivered'
  | 'completed'
  | 'rejected'

export type AuthProvider = 'password' | 'google'

export interface User {
  id: number
  name: string
  email: string
  role: Role
  is_active: boolean
  created_at: string
  auth_provider: AuthProvider
  avatar_url: string | null
  last_login: string | null
}

/** Public config that decides what the login page offers. */
export interface AuthConfig {
  google_enabled: boolean
  google_client_id: string
  self_signup_enabled: boolean
  password_reset_enabled: boolean
  allowed_email_domains: string[]
}

export interface Contact {
  id: number
  company_name: string
  /** Optional: marketplace RFQs often omit it. */
  country: string | null
  contact_person: string | null
  email: string | null
  phone: string | null
  whatsapp: string | null
  trade_type: TradeType
  coffee_product: string | null
  quantity_kg: number | null
  /** The requirement in the buyer's own words. */
  quantity_note: string | null
  roast_preference: string | null
  bean_type: string | null
  estimated_value_usd: number | null
  hs_code: string | null
  shipping_terms: string | null
  destination_port: string | null
  payment_terms: string | null
  origin_preference: string | null
  sourcing_from: string | null
  rfq_source: string | null
  rfq_reference: string | null
  status: DealStatus
  notes: string | null
  owner_id: number | null
  owner: User | null
  last_contacted_at: string | null
  next_follow_up: string | null
  created_at: string
  updated_at: string
  activity_count: number
  document_count: number
}

export interface ContactDetail extends Contact {
  activities: Activity[]
  documents: DocumentFile[]
  reminders: Reminder[]
}

export interface Activity {
  id: number
  contact_id: number
  user_id: number | null
  occurred_at: string
  channel: Channel
  discussion: string
  customer_reply: string | null
  ai_summary: string | null
  next_follow_up: string | null
  status_after: DealStatus | null
  created_at: string
  user: User | null
  contact_company: string | null
}

export interface DocumentFile {
  id: number
  contact_id: number
  doc_type: DocType
  original_name: string
  content_type: string | null
  size_bytes: number
  note: string | null
  created_at: string
  uploaded_by_id: number | null
  download_url: string
}

export interface Reminder {
  id: number
  contact_id: number
  due_date: string
  message: string
  source: 'manual' | 'ai'
  priority: 'low' | 'medium' | 'high'
  is_done: boolean
  created_at: string
  contact_company: string | null
}

export interface Kpis {
  new_leads: number
  export_orders: number
  import_orders: number
  shipments_in_progress: number
  completed_orders: number
  pending_follow_ups: number
  total_contacts: number
  activities_today: number
  conversion_rate: number
  pipeline_value_usd: number
}

export interface CountryStat {
  country: string
  /** Quotes / enquiries filed under this country. */
  count: number
  /** Cold-outreach prospects — counted separately, never summed into `count`. */
  prospects: number
  value_usd: number
}

/** One entry in the shared country picker, merged across quotes and outreach. */
export interface CountryOption {
  name: string
  quotes: number
  prospects: number
}

export interface StatusStat {
  status: DealStatus
  count: number
}

export interface TrendPoint {
  label: string
  activities: number
  new_leads: number
}

export interface DashboardFilterState {
  country: string | null
  trade_type: 'export' | 'import' | null
  days: number
  date_from: string | null
  date_to: string | null
  /** 1 = a point per day, 7 = per week, 30 = per calendar month. */
  bucket_days: number
}

export interface Dashboard {
  greeting: string
  kpis: Kpis
  /** Never narrowed by the country filter — it is the chart you pick from. */
  by_country: CountryStat[]
  by_status: StatusStat[]
  /** Money per stage, keyed by DealStatus — the counts chart cannot say this. */
  value_by_status: Record<string, number>
  /** Cold list -> replied -> quote -> order. Each step a subset of the last. */
  funnel: { stage: string; count: number }[]
  trend: TrendPoint[]
  export_vs_import: { export: number; import: number }
  recent_activities: Activity[]
  upcoming_follow_ups: Reminder[]
  filters: DashboardFilterState
  /** Totals for the chosen window, unlike the current-state KPIs. */
  period: { activities?: number; new_leads?: number }
}

export interface Insight {
  content: string
  model: string
  generated_at: string
  cached: boolean
  ai_enabled: boolean
}

export interface Suggestion {
  contact_id: number
  company_name: string
  country: string
  status: DealStatus
  priority: 'low' | 'medium' | 'high'
  reason: string
  suggested_action: string
  days_since_contact: number | null
}

export interface LeaderboardRow {
  user_id: number
  name: string
  activities: number
}


/* ------------------------------------------------------------- outreach */

export type ContactMethod =
  | 'linkedin'
  | 'email'
  | 'website_form'
  | 'instagram'
  | 'phone'
  | 'whatsapp'
  | 'other'

export type OutreachStatus =
  | 'follow_up_needed'
  | 'follow_up_sent'
  | 'waiting_reply'
  | 'replied'
  | 'no_response'
  | 'not_interested'

/** One company we contacted, and everything that came back. */
export interface Outreach {
  id: number
  company_name: string
  contact_person: string | null
  website: string | null
  email: string | null
  country: string | null
  contact_method: ContactMethod
  /** The exact place: a LinkedIn URL, the contact-form page, an inbox. */
  contact_point: string | null
  contacted_on: string | null
  message_sent: string | null
  status: OutreachStatus
  their_reply: string | null
  replied_on: string | null
  next_action: string | null
  next_follow_up: string | null
  follow_ups_sent: number
  notes: string | null
  owner_id: number | null
  owner: User | null
  quote_id: number | null
  created_at: string
  updated_at: string
}

export interface OutreachStats {
  total: number
  awaiting_reply: number
  replied: number
  due_today: number
  overdue: number
  no_response: number
  not_interested: number
  reply_rate: number
  by_method: Record<string, number>
}

export interface OutreachGroup {
  label: string
  total: number
  replied: number
  awaiting: number
  reply_rate: number
  follow_ups: number
}

/**
 * A row as the list draws it. Missing on purpose: `message_sent`, `notes` and
 * the nested `owner` — 70% of the old payload, none of it rendered here. The
 * editor fetches the full `Outreach` by id when it opens.
 */
export type OutreachRow = Omit<Outreach, 'message_sent' | 'notes' | 'owner'>

/* ------------------------------------------------------ automated outreach */

export interface EmailAccount {
  id: number
  from_email: string
  from_name: string
  /** smtp | resend | brevo — how the message physically leaves. */
  provider: 'smtp' | 'resend' | 'brevo'
  /** Where replies land when the From address is not the mailbox you read. */
  reply_to: string | null
  smtp_host: string
  smtp_port: number
  smtp_user: string
  use_starttls: boolean
  daily_limit: number
  /** Whether a secret is stored. The secret itself is never sent here. */
  has_password: boolean
  has_api_key: boolean
  last_verified_at: string | null
  last_error: string | null

  /** The mailbox replies are read from, over IMAP. */
  imap_host: string
  imap_port: number
  imap_user: string
  has_imap_password: boolean
  reply_check_enabled: boolean
  last_reply_check_at: string | null
  last_reply_error: string | null
}

/** A message a customer sent back, and what the app made of it. */
export interface InboundReply {
  id: number
  message_id: string
  from_email: string | null
  from_name: string | null
  subject: string | null
  received_at: string
  body: string | null
  /** thread = proved by the header we sent. address = the sender matches. */
  match_kind: 'thread' | 'address' | 'manual' | 'unmatched'
  classification: string
  classified_by: string
  outreach_id: number | null
  campaign_id: number | null
  company_name: string | null
  suggested_reply: string | null
  handled: boolean
  sent_at: string | null
  reply_speed_hours: number | null
}

export interface ReplySync {
  checked: number
  stored: number
  matched: number
  unmatched: number
  skipped: number
  error: string | null
}

export interface EmailTemplate {
  id: number
  name: string
  subject: string
  body: string
  instructions: string | null
  placeholders: string[]
  created_at: string
  updated_at: string
}

export interface ImportReport {
  file_rows: number
  addresses: number
  companies: number
  multi_address_companies: number
  duplicate_addresses: number
  without_email: number
  invalid_emails: number
  possible_duplicates: string[]
  unmapped_columns: string[]
  /** The same company name on more than one row. */
  repeated_companies: string[]
  /** Different company names at one address. */
  shared_locations: string[]
}

export type CampaignState =
  | 'draft'
  | 'running'
  | 'paused'
  | 'daily_limit'
  | 'completed'
  | 'stopped'

export interface Campaign {
  id: number
  name: string
  status: CampaignState
  mode: 'manual' | 'automatic'
  daily_limit: number
  template_id: number | null
  source_filename: string | null
  created_at: string
  last_activity_at: string | null
}

export interface CampaignStatus {
  campaign_id: number
  name: string
  status: CampaignState
  mode: 'manual' | 'automatic'
  total: number
  companies: number
  companies_contacted: number
  multi_address_companies: number
  processed: number
  sent: number
  failed: number
  duplicates: number
  skipped: number
  unverified: number
  awaiting_approval: number
  remaining: number
  percent: number
  daily_limit: number
  sent_today: number
  remaining_today: number
  last_company: string | null
  next_company: string | null
  next_target_id: number | null
  last_activity_at: string | null
}

export type TargetState =
  | 'pending'
  | 'processing'
  | 'awaiting_approval'
  | 'sent'
  | 'failed'
  | 'duplicate'
  | 'skipped'
  | 'cancelled'
  | 'unverified'

export interface CampaignTarget {
  id: number
  position: number
  company_name: string
  email: string | null
  country: string | null
  website: string | null
  contact_person: string | null
  state: TargetState
  skip_reason: string | null
  prepared_subject: string | null
  prepared_body: string | null
  attempts: number
  last_error: string | null
  sent_at: string | null
  outreach_id: number | null
}

export interface SendAttempt {
  id: number
  target_id: number
  attempt_no: number
  to_email: string | null
  subject: string | null
  status: string
  error: string | null
  message_id: string | null
  started_at: string
  finished_at: string | null
  company_name: string | null
}

export interface CampaignEvent {
  id: number
  kind: string
  message: string
  at: string
  target_id: number | null
}

export interface StepResult {
  steps: { action: string; message: string; company: string | null; email: string | null }[]
  status: CampaignStatus
}

export interface OutreachInsights {
  by_country: OutreachGroup[]
  countries_tracked: number
  companies_tracked: number
}

/* --------------------------------------------------- the durable report */

export interface DaySummary {
  day: string
  sent: number
  failed: number
  duplicates: number
  skipped: number
  limit: number
  /** Companies, not addresses — several mailboxes at one firm count once. */
  companies: number
  campaigns: string[]
  sent_to: { company: string; email: string | null; at: string; country: string | null }[]
  not_sent: { company: string; email: string | null; outcome: string; reason: string | null }[]
}

export interface DailyReport {
  totals: {
    sent: number
    failed: number
    duplicates: number
    skipped: number
    companies: number
    today: { sent: number; limit: number; remaining: number; failed: number }
  }
  days: DaySummary[]
}

/** Companies sharing a name but differing in address, domain or mailbox. */
export interface DuplicateGroup {
  name: string
  spellings: string[]
  locations: string[]
  emails: string[]
  websites: string[]
  differs_by: string[]
  contacted: number
  skipped_as_duplicate: number
}

/** Sends and replies by month, country against month, and reply speed. */
export interface TrendReport {
  months: string[]
  by_month: { month: string; label: string; sent: number; replied: number }[]
  country_by_month: { country: string; cells: number[] }[]
  response_days: { bucket: string; count: number }[]
  replies_counted: number
}

/** One company sitting on more than one row of the outreach log. */
export interface MergeGroup {
  company_name: string
  country: string | null
  rows: number
  emails: string[]
  ids: number[]
}

/** A combine that has not been undone yet. */
export interface MergeUndo {
  id: number
  at: string
  companies: number
  rows_removed: number
}

/** One company as it was combined: the rows that went in, the row that came out. */
export interface MergedInto {
  company_name: string
  country: string | null
  absorbed_emails: string[]
  kept_email: string | null
}

/** One press of Combine. */
export interface MergeHistory {
  id: number
  at: string
  companies: number
  rows_removed: number
  undone: boolean
  details: MergedInto[]
}
