import type { Channel, DealStatus, DocType, TradeType } from './types'

/**
 * Status colours for chips, badges and pipeline column headers.
 *
 * These are *status* colours, not a data ramp: every one is measured at
 * ≥4.5:1 against the dark app surface (#2A1A12), and each always ships beside
 * its text label so state never depends on colour alone.
 *
 * Deliberately NOT a straight roast ramp — the deep-roast end of the brand
 * palette (#6F4E37 down to #3B2416) measures 2.25:1 to 1.16:1 here, which is
 * unreadable. The progression instead runs warm (prospecting) → green
 * (committed) → blue (in transit) → green (delivered), with red for rejected.
 * The roast ramp still carries magnitude in the charts (see lib/viz.ts).
 */
export const STATUS_META: Record<
  DealStatus,
  { label: string; hex: string; text: string; ring: string }
> = {
  new_lead: { label: 'New Lead', hex: '#E8D5BC', text: 'text-crema', ring: 'border-crema/40' },
  contacted: { label: 'Contacted', hex: '#DCAB63', text: 'text-gold', ring: 'border-gold/40' },
  quotation_sent: {
    label: 'Quotation Sent',
    hex: '#D9A05B',
    text: 'text-gold',
    ring: 'border-gold/45',
  },
  sample_sent: {
    label: 'Sample Sent',
    hex: '#C99A6B',
    text: 'text-caramel',
    ring: 'border-caramel/45',
  },
  negotiation: {
    label: 'Negotiation',
    hex: '#E0A458',
    text: 'text-caramel',
    ring: 'border-caramel/50',
  },
  order_confirmed: {
    label: 'Order Confirmed',
    hex: '#5FD3A0',
    text: 'text-emerald-300',
    ring: 'border-emerald-400/40',
  },
  production: { label: 'Production', hex: '#7FC7E8', text: 'text-sky-300', ring: 'border-sky-400/40' },
  shipment_in_progress: {
    label: 'Shipment in Progress',
    hex: '#5AA9E6',
    text: 'text-sky-300',
    ring: 'border-sky-400/40',
  },
  delivered: {
    label: 'Delivered',
    hex: '#7EDCB0',
    text: 'text-emerald-300',
    ring: 'border-emerald-400/40',
  },
  completed: {
    label: 'Completed',
    hex: '#4FD18B',
    text: 'text-emerald-300',
    ring: 'border-emerald-400/50',
  },
  rejected: { label: 'Rejected', hex: '#EA8C8C', text: 'text-red-300', ring: 'border-red-400/40' },
}

export const STATUS_ORDER: DealStatus[] = [
  'new_lead',
  'contacted',
  'quotation_sent',
  'sample_sent',
  'negotiation',
  'order_confirmed',
  'production',
  'shipment_in_progress',
  'delivered',
  'completed',
  'rejected',
]

export const CHANNEL_META: Record<Channel, { label: string; icon: string }> = {
  call: { label: 'Call', icon: '📞' },
  email: { label: 'Email', icon: '✉️' },
  whatsapp: { label: 'WhatsApp', icon: '💬' },
  meeting: { label: 'Meeting', icon: '🤝' },
  linkedin: { label: 'LinkedIn', icon: '🔗' },
  other: { label: 'Other', icon: '☕' },
}

export const DOC_TYPE_LABEL: Record<DocType, string> = {
  quotation: 'Quotation PDF',
  invoice: 'Invoice',
  purchase_order: 'Purchase Order',
  email_screenshot: 'Email Screenshot',
  meeting_screenshot: 'Meeting Screenshot',
  sample_photo: 'Product Sample Photo',
  other: 'Other',
}

export const TRADE_LABEL: Record<TradeType, string> = { export: 'Export', import: 'Import' }

export function statusLabel(s: DealStatus) {
  return STATUS_META[s]?.label ?? s
}

export function money(value: number | null | undefined) {
  if (value === null || value === undefined) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value)
}

export function compactMoney(value: number | null | undefined) {
  if (value === null || value === undefined) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value)
}

export function kg(value: number | null | undefined) {
  if (value === null || value === undefined) return '—'
  if (value >= 1000) return `${(value / 1000).toLocaleString('en-US', { maximumFractionDigits: 1 })} t`
  return `${value.toLocaleString('en-US')} kg`
}

export function formatDate(value: string | null | undefined) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** "3 days ago" / "in 2 days" — used across timelines and reminder lists. */
export function relativeDays(value: string | null | undefined) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  const startOf = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
  const diff = Math.round((startOf(d) - startOf(new Date())) / 86_400_000)
  if (diff === 0) return 'Today'
  if (diff === 1) return 'Tomorrow'
  if (diff === -1) return 'Yesterday'
  if (diff < 0) return `${Math.abs(diff)} days ago`
  return `in ${diff} days`
}

export function daysSince(value: string | null | undefined): number | null {
  if (!value) return null
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return null
  return Math.floor((Date.now() - d.getTime()) / 86_400_000)
}

export function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

export function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? '')
    .join('')
}

/** Rough centroid per country, for the world-map markers. */
export const COUNTRY_COORDS: Record<string, [number, number]> = {
  germany: [10.4, 51.2],
  sweden: [15.6, 62.0],
  turkey: [35.2, 39.0],
  japan: [138.3, 36.2],
  uae: [54.0, 24.0],
  'united arab emirates': [54.0, 24.0],
  kenya: [37.9, -0.02],
  brazil: [-51.9, -14.2],
  vietnam: [108.3, 14.1],
  colombia: [-74.3, 4.6],
  canada: [-106.3, 56.1],
  italy: [12.6, 41.9],
  australia: [133.8, -25.3],
  india: [78.9, 20.6],
  ethiopia: [40.5, 9.1],
  indonesia: [113.9, -0.8],
  usa: [-95.7, 37.1],
  'united states': [-95.7, 37.1],
  uk: [-3.4, 55.4],
  'united kingdom': [-3.4, 55.4],
  france: [2.2, 46.2],
  spain: [-3.7, 40.5],
  netherlands: [5.3, 52.1],
  poland: [19.1, 51.9],
  ireland: [-8.2, 53.4],
  china: [104.2, 35.9],
  'south korea': [127.8, 35.9],
  singapore: [103.8, 1.35],
  'saudi arabia': [45.1, 23.9],
  egypt: [30.8, 26.8],
  'south africa': [22.9, -30.6],
  mexico: [-102.6, 23.6],
  peru: [-75.0, -9.2],
  honduras: [-86.2, 15.2],
  guatemala: [-90.2, 15.8],
  uganda: [32.3, 1.4],
  tanzania: [34.9, -6.4],
  rwanda: [29.9, -1.9],
  switzerland: [8.2, 46.8],
  belgium: [4.5, 50.5],
  norway: [8.5, 60.5],
  denmark: [9.5, 56.3],
  finland: [25.7, 61.9],
  russia: [105.3, 61.5],
  thailand: [100.9, 15.9],
  malaysia: [101.98, 4.2],
  philippines: [121.8, 12.9],
  'new zealand': [174.9, -40.9],
}

/** Equirectangular projection → percentage offsets for absolute positioning. */
export function projectToPercent(lon: number, lat: number) {
  return { left: ((lon + 180) / 360) * 100, top: ((90 - lat) / 180) * 100 }
}

export function coordsFor(country: string): [number, number] | null {
  return COUNTRY_COORDS[country.trim().toLowerCase()] ?? null
}
