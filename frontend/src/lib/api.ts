/** Thin typed fetch wrapper around the BeviGrow API. */
import type {
  Activity,
  Contact,
  ContactDetail,
  Dashboard,
  DealStatus,
  DocumentFile,
  Insight,
  LeaderboardRow,
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

export const api = {
  // ---- auth
  login: (email: string, password: string) =>
    request<{ access_token: string; user: User }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<User>('/api/auth/me'),

  // ---- users
  listUsers: () => request<User[]>('/api/users'),
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

  // ---- dashboard
  dashboard: () => request<Dashboard>('/api/dashboard'),
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
