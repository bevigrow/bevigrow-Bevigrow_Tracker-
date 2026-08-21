/** Thin typed fetch wrapper around the BeviGrow API. */
import type {
  Activity,
  AuthConfig,
  Campaign,
  CampaignEvent,
  CampaignStatus,
  CampaignTarget,
  Contact,
  ContactDetail,
  CountryOption,
  DailyReport,
  Dashboard,
  DuplicateGroup,
  EmailAccount,
  EmailTemplate,
  ImportReport,
  SendAttempt,
  StepResult,
  DealStatus,
  DocumentFile,
  Insight,
  LeaderboardRow,
  Outreach,
  OutreachInsights,
  OutreachRow,
  OutreachStats,
  Reminder,
  Suggestion,
  User,
} from './types'

// In production this is baked in at build time by Vite (VITE_API_URL).
// In dev it stays empty so requests hit the Vite proxy on the same origin.
//
// Render's `fromService` substitution yields a bare hostname
// ("bevigrow-backend.onrender.com"), so add the scheme when it is missing —
// otherwise every request resolves as a relative path and 404s.
const rawApiBase = (import.meta.env.VITE_API_URL ?? '').trim().replace(/\/+$/, '')
export const API_BASE =
  rawApiBase && !/^https?:\/\//i.test(rawApiBase) ? `https://${rawApiBase}` : rawApiBase

/**
 * A production build with no VITE_API_URL is always a misconfiguration.
 *
 * Left unchecked it fails in a way that is very hard to diagnose: API_BASE is
 * "", so every request goes to the static site's own origin, the SPA rewrite
 * answers /api/* with index.html, and the user just sees a generic connection
 * error. Naming the real problem here saves a long hunt.
 */
export const API_MISCONFIGURED = import.meta.env.PROD && !API_BASE

if (API_MISCONFIGURED) {
  console.error(
    '[BeviGrow] VITE_API_URL was empty when this bundle was built, so the app ' +
      'has no backend address and is calling itself. Set VITE_API_URL on the ' +
      'frontend service to the backend URL, then REBUILD — Vite inlines this ' +
      'value at build time, so a restart is not enough.',
  )
}

const TOKEN_KEY = 'bevigrow.token'

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

/** Fires when a 401 comes back, so the auth provider can log the user out. */
const unauthorizedListeners = new Set<() => void>()
export function onUnauthorized(fn: () => void): () => void {
  unauthorizedListeners.add(fn)
  return () => {
    unauthorizedListeners.delete(fn)
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  const token = tokenStore.get()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  if (API_MISCONFIGURED) {
    throw new ApiError(
      'This build has no backend address (VITE_API_URL was empty at build ' +
        'time), so it is calling itself instead of the API. Set VITE_API_URL ' +
        'on the frontend service and redeploy.',
      0,
    )
  }

  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init, headers })
  } catch {
    throw new ApiError('Cannot reach the BeviGrow server. Check your connection.', 0)
  }

  // A 401 from the login endpoint means "wrong credentials", not "session
  // expired" — it must surface the server's message and must NOT trigger the
  // global sign-out, or a failed sign-in attempt reports itself as a timeout.
  const isLoginAttempt = path.startsWith('/api/auth/login') || path.startsWith('/api/auth/token')

  if (res.status === 401 && !isLoginAttempt) {
    tokenStore.clear()
    unauthorizedListeners.forEach((fn) => fn())
    throw new ApiError('Your session has expired. Please sign in again.', 401)
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') detail = body.detail
      else if (Array.isArray(body.detail) && body.detail[0]?.msg) {
        // FastAPI validation errors
        detail = body.detail
          .map((e: { loc?: (string | number)[]; msg: string }) =>
            e.loc?.length ? `${e.loc[e.loc.length - 1]}: ${e.msg}` : e.msg,
          )
          .join('; ')
      }
    } catch {
      /* non-JSON error body — keep the generic message */
    }
    throw new ApiError(detail, res.status)
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

const qs = (params: Record<string, unknown>) => {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') sp.set(k, String(v))
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}

export interface ContactFilters {
  search?: string
  trade_type?: string
  status?: string
  country?: string
  owner_id?: number
}

export interface DashboardFilters {
  country?: string
  trade_type?: string
  /** Length of the activity trend window, in days. */
  days?: number
  /** Or an explicit range, which wins over `days`. */
  date_from?: string
  date_to?: string
}

export const api = {
  // ---- auth
  authConfig: () => request<AuthConfig>('/api/auth/config'),
  login: (email: string, password: string) =>
    request<{ access_token: string; user: User }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  loginWithGoogle: (credential: string) =>
    request<{ access_token: string; user: User }>('/api/auth/google', {
      method: 'POST',
      body: JSON.stringify({ credential }),
    }),
  signup: (name: string, email: string, password: string) =>
    request<{ access_token: string; user: User }>('/api/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ name, email, password }),
    }),
  forgotPassword: (email: string) =>
    request<{ message: string; email_sent: boolean }>('/api/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),
  resetPassword: (token: string, new_password: string) =>
    request<{ access_token: string; user: User }>('/api/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password }),
    }),
  me: () => request<User>('/api/auth/me'),
  updateProfile: (name: string) =>
    request<User>('/api/auth/me', { method: 'PATCH', body: JSON.stringify({ name }) }),
  changePassword: (current_password: string, new_password: string) =>
    request<User>('/api/auth/me/password', {
      method: 'POST',
      body: JSON.stringify({ current_password, new_password }),
    }),

  // ---- users
  listUsers: (f: { search?: string; role?: string; is_active?: boolean } = {}) =>
    request<User[]>(`/api/users${qs({ ...f })}`),
  adminResetPassword: (id: number, new_password: string) =>
    request<User>(`/api/users/${id}/reset-password`, {
      method: 'POST',
      body: JSON.stringify({ new_password }),
    }),
  createUser: (body: { name: string; email: string; password: string; role: string }) =>
    request<User>('/api/users', { method: 'POST', body: JSON.stringify(body) }),
  updateUser: (id: number, body: Record<string, unknown>) =>
    request<User>(`/api/users/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteUser: (id: number) => request<void>(`/api/users/${id}`, { method: 'DELETE' }),

  // ---- contacts
  listContacts: (f: ContactFilters = {}) => request<Contact[]>(`/api/contacts${qs({ ...f })}`),
  getContact: (id: number) => request<ContactDetail>(`/api/contacts/${id}`),
  createContact: (body: Record<string, unknown>) =>
    request<Contact>('/api/contacts', { method: 'POST', body: JSON.stringify(body) }),
  updateContact: (id: number, body: Record<string, unknown>) =>
    request<Contact>(`/api/contacts/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteContact: (id: number) => request<void>(`/api/contacts/${id}`, { method: 'DELETE' }),
  countries: () => request<string[]>('/api/contacts/countries'),
  /** Every country known to the app — quotes and cold outreach alike. */
  countryOptions: () => request<CountryOption[]>('/api/countries'),
  pipeline: (trade_type?: string) =>
    request<Record<DealStatus, Contact[]>>(`/api/contacts/board/pipeline${qs({ trade_type })}`),

  // ---- activities
  listActivities: (f: Record<string, unknown> = {}) =>
    request<Activity[]>(`/api/activities${qs(f)}`),
  createActivity: (body: Record<string, unknown>) =>
    request<Activity>('/api/activities', { method: 'POST', body: JSON.stringify(body) }),
  updateActivity: (id: number, body: Record<string, unknown>) =>
    request<Activity>(`/api/activities/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  resummarize: (id: number) =>
    request<Activity>(`/api/activities/${id}/summarize`, { method: 'POST' }),
  deleteActivity: (id: number) => request<void>(`/api/activities/${id}`, { method: 'DELETE' }),

  // ---- documents
  listDocuments: (f: Record<string, unknown> = {}) =>
    request<DocumentFile[]>(`/api/documents${qs(f)}`),
  uploadDocument: (form: FormData) =>
    request<DocumentFile>('/api/documents', { method: 'POST', body: form }),
  deleteDocument: (id: number) => request<void>(`/api/documents/${id}`, { method: 'DELETE' }),
  /** Auth-aware download — the API needs the bearer token, so fetch then save. */
  downloadDocument: async (doc: DocumentFile) => {
    const res = await fetch(`${API_BASE}${doc.download_url}`, {
      headers: { Authorization: `Bearer ${tokenStore.get() ?? ''}` },
    })
    if (!res.ok) throw new ApiError('Download failed', res.status)
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = doc.original_name
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },

  // ---- reminders
  listReminders: (f: Record<string, unknown> = {}) => request<Reminder[]>(`/api/reminders${qs(f)}`),
  createReminder: (body: Record<string, unknown>) =>
    request<Reminder>('/api/reminders', { method: 'POST', body: JSON.stringify(body) }),
  updateReminder: (id: number, body: Record<string, unknown>) =>
    request<Reminder>(`/api/reminders/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteReminder: (id: number) => request<void>(`/api/reminders/${id}`, { method: 'DELETE' }),

  // ---- outreach
  listOutreach: (f: Record<string, unknown> = {}) => request<OutreachRow[]>(`/api/outreach${qs(f)}`),
  /** The full record, including the message we sent — fetched when you open one. */
  getOutreach: (id: number) => request<Outreach>(`/api/outreach/${id}`),
  outreachStats: () => request<OutreachStats>('/api/outreach/stats'),
  createOutreach: (body: Record<string, unknown>) =>
    request<Outreach>('/api/outreach', { method: 'POST', body: JSON.stringify(body) }),
  updateOutreach: (id: number, body: Record<string, unknown>) =>
    request<Outreach>(`/api/outreach/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteOutreach: (id: number) => request<void>(`/api/outreach/${id}`, { method: 'DELETE' }),
  logFollowUp: (id: number, days = 7) =>
    request<Outreach>(`/api/outreach/${id}/follow-up${qs({ days_until_next: days })}`, {
      method: 'POST',
    }),

  convertToQuote: (id: number) =>
    request<Contact>(`/api/outreach/${id}/convert`, { method: 'POST' }),

  outreachInsights: (limit?: number) =>
    request<OutreachInsights>(`/api/outreach/insights${qs({ limit })}`),

  // ---- automated outreach
  emailAccount: () => request<EmailAccount | null>('/api/email-account'),
  saveEmailAccount: (body: Record<string, unknown>) =>
    request<EmailAccount>('/api/email-account', { method: 'PUT', body: JSON.stringify(body) }),
  verifyEmailAccount: () =>
    request<EmailAccount>('/api/email-account/verify', { method: 'POST' }),

  listTemplates: () => request<EmailTemplate[]>('/api/templates'),
  createTemplate: (body: Record<string, unknown>) =>
    request<EmailTemplate>('/api/templates', { method: 'POST', body: JSON.stringify(body) }),
  updateTemplate: (id: number, body: Record<string, unknown>) =>
    request<EmailTemplate>(`/api/templates/${id}`, { method: 'PUT', body: JSON.stringify(body) }),

  listCampaigns: (deleted = false) => request<Campaign[]>(`/api/campaigns${qs({ deleted })}`),
  restoreCampaign: (id: number) =>
    request<CampaignStatus>(`/api/campaigns/${id}/restore`, { method: 'POST' }),
  purgeCampaign: (id: number) =>
    request<void>(`/api/campaigns/${id}/purge`, { method: 'DELETE' }),
  dailyReport: (days = 30) => request<DailyReport>(`/api/campaigns/report/daily${qs({ days })}`),
  duplicateReport: () => request<DuplicateGroup[]>('/api/campaigns/report/duplicates'),
  importCampaign: (form: FormData) =>
    request<{ campaign: Campaign; report: ImportReport }>('/api/campaigns/import', {
      method: 'POST',
      body: form,
    }),
  campaignStatus: (id: number) => request<CampaignStatus>(`/api/campaigns/${id}`),
  deleteCampaign: (id: number) => request<void>(`/api/campaigns/${id}`, { method: 'DELETE' }),
  outreachChat: (message: string, campaign_id?: number) =>
    request<{ reply: string; action: string; acted: boolean; campaign_id: number | null }>(
      '/api/campaigns/chat',
      { method: 'POST', body: JSON.stringify({ message, campaign_id }) },
    ),
  outreachHealth: () =>
    request<{
      scheduler_running: boolean
      heartbeat_configured: boolean
      mailbox_connected: boolean
      mailbox_verified: boolean
      campaigns_active: number
      sent_today: number
      daily_limit: number
    }>('/api/campaigns/system/health'),
  updateCampaign: (id: number, f: { mode?: string; daily_limit?: number }) =>
    request<CampaignStatus>(`/api/campaigns/${id}${qs({ ...f })}`, { method: 'PATCH' }),
  startCampaign: (id: number) =>
    request<CampaignStatus>(`/api/campaigns/${id}/start`, { method: 'POST' }),
  pauseCampaign: (id: number) =>
    request<CampaignStatus>(`/api/campaigns/${id}/pause`, { method: 'POST' }),
  stopCampaign: (id: number) =>
    request<CampaignStatus>(`/api/campaigns/${id}/stop`, { method: 'POST' }),
  /** Advance the queue. The Start button calls this on a timer while running. */
  stepCampaign: (id: number, count = 1) =>
    request<StepResult>(`/api/campaigns/${id}/step${qs({ count })}`, { method: 'POST' }),
  campaignQueue: (id: number, f: { state?: string; limit?: number; offset?: number } = {}) =>
    request<CampaignTarget[]>(`/api/campaigns/${id}/queue${qs({ ...f })}`),
  campaignAttempts: (id: number, limit = 100) =>
    request<SendAttempt[]>(`/api/campaigns/${id}/attempts${qs({ limit })}`),
  campaignEvents: (id: number, limit = 50) =>
    request<CampaignEvent[]>(`/api/campaigns/${id}/events${qs({ limit })}`),
  approveTarget: (id: number, targetId: number) =>
    request<StepResult>(`/api/campaigns/${id}/targets/${targetId}/approve`, { method: 'POST' }),
  skipTarget: (id: number, targetId: number, reason: string) =>
    request<StepResult>(
      `/api/campaigns/${id}/targets/${targetId}/skip${qs({ reason })}`,
      { method: 'POST' },
    ),
  retryTarget: (id: number, targetId: number) =>
    request<StepResult>(`/api/campaigns/${id}/targets/${targetId}/retry`, { method: 'POST' }),

  // ---- dashboard
  dashboard: (f: DashboardFilters = {}) => request<Dashboard>(`/api/dashboard${qs({ ...f })}`),
  leaderboard: (days = 30) => request<LeaderboardRow[]>(`/api/dashboard/leaderboard${qs({ days })}`),

  // ---- ai (Claude Haiku)
  aiStatus: () => request<{ ai_enabled: boolean; model: string; note: string }>('/api/ai/status'),
  summarize: (notes: string, company_name?: string, country?: string) =>
    request<{ summary: string; model: string; ai_enabled: boolean }>('/api/ai/summarize', {
      method: 'POST',
      body: JSON.stringify({ notes, company_name, country }),
    }),
  insights: (refresh = false) => request<Insight>(`/api/ai/insights${qs({ refresh })}`),
  weekly: (refresh = false) => request<Insight>(`/api/ai/weekly${qs({ refresh })}`),
  suggestions: () =>
    request<{ suggestions: Suggestion[]; model: string; ai_enabled: boolean }>(
      '/api/ai/suggestions',
    ),
  applySuggestions: () => request<number[]>('/api/ai/suggestions/apply', { method: 'POST' }),
}
