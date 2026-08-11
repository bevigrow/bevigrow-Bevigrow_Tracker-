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
  count: number
  value_usd: number
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

export interface Dashboard {
  greeting: string
  kpis: Kpis
  by_country: CountryStat[]
  by_status: StatusStat[]
  trend: TrendPoint[]
  export_vs_import: { export: number; import: number }
  recent_activities: Activity[]
  upcoming_follow_ups: Reminder[]
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

export interface OutreachInsights {
  by_country: OutreachGroup[]
  countries_tracked: number
  companies_tracked: number
}
