import {
  CircleSlash,
  Clock,
  FilePlus2,
  Globe,
  MailCheck,
  Plus,
  Search,
  Send,
  Trash2,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import {
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  Field,
  Input,
  Modal,
  Select,
  Skeleton,
  Textarea,
} from '../components/ui'
import { CountryInput, forgetCountries, knownCountries } from '../components/CountryInput'
import { OutreachInsights } from '../components/OutreachInsights'
import { ApiError, api } from '../lib/api'
import {
  METHOD_META,
  METHOD_ORDER,
  OUTREACH_META,
  OUTREACH_ORDER,
  formatDate,
  outreachLabel,
  relativeDays,
} from '../lib/format'
import { useToast } from '../lib/toast'
import type {
  ContactMethod,
  CountryOption,
  Outreach as FullRow,
  MergeGroup,
  CountrySent,
  OutreachRow as Row,
  OutreachInsights as Insights,
  OutreachStats,
  OutreachStatus,
} from '../lib/types'

/** The two dates a chosen period means.
 *
 * The picker offers words — "this month", "August 2026", "2025" — and the
 * filter takes a pair of dates, because that is the shape every one of those
 * questions really has. Doing the arithmetic here rather than on the server
 * keeps the API to one honest parameter pair instead of a vocabulary of
 * period names it would have to keep in step with this list.
 */
function windowFor(period: string): { from?: string; to?: string } {
  if (!period) return {}
  const iso = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  const today = new Date()

  if (period === 'today') return { from: iso(today), to: iso(today) }
  if (period === 'last7') {
    const from = new Date(today)
    from.setDate(from.getDate() - 6)
    return { from: iso(from), to: iso(today) }
  }
  if (period === 'last30') {
    const from = new Date(today)
    from.setDate(from.getDate() - 29)
    return { from: iso(from), to: iso(today) }
  }
  if (period === 'thismonth') {
    return {
      from: iso(new Date(today.getFullYear(), today.getMonth(), 1)),
      to: iso(new Date(today.getFullYear(), today.getMonth() + 1, 0)),
    }
  }
  if (period === 'lastmonth') {
    return {
      from: iso(new Date(today.getFullYear(), today.getMonth() - 1, 1)),
      to: iso(new Date(today.getFullYear(), today.getMonth(), 0)),
    }
  }
  // "2026-08" — one month. Day 0 of the next month is the last of this one,
  // which is how February and the leap years take care of themselves.
  if (/^\d{4}-\d{2}$/.test(period)) {
    const [y, m] = period.split('-').map(Number)
    return { from: iso(new Date(y, m - 1, 1)), to: iso(new Date(y, m, 0)) }
  }
  // "2026" — a whole year.
  if (/^\d{4}$/.test(period)) {
    return { from: `${period}-01-01`, to: `${period}-12-31` }
  }
  return {}
}

/** A note pinned to the corner: countries, and companies written to in each.
 *
 * Counted from the send history rather than from the log underneath it. The
 * log holds a row per mailbox when a company is saved that way, so counting
 * its rows says a firm with two addresses is two firms — which is exactly the
 * error this note exists to avoid. The ledger knows which addresses belonged
 * to one business, because that is how the importer grouped them before
 * anything was sent.
 *
 * Small, fixed, and collapsible to a single line, because it is meant to be
 * glanced at while reading something else — not a panel to be scrolled past
 * on the way to the list.
 */
function CountryNote({ rows }: { rows: CountrySent[] }) {
  const [open, setOpen] = useState(() => {
    try {
      return localStorage.getItem('bevigrow.countryNote') !== 'closed'
    } catch {
      return true
    }
  })
  if (rows.length === 0) return null

  const companies = rows.reduce((n, r) => n + r.companies, 0)
  const emails = rows.reduce((n, r) => n + r.emails, 0)

  const toggle = () => {
    setOpen((v) => {
      try {
        localStorage.setItem('bevigrow.countryNote', v ? 'closed' : 'open')
      } catch {
        /* a browser refusing storage is not a reason to refuse the click */
      }
      return !v
    })
  }

  return (
    <aside
      className="fixed bottom-4 right-4 z-40 w-[15.5rem] rounded-xl border border-gold/25 bg-[#1b140f] shadow-xl shadow-black/40"
      aria-label="Companies written to, by country"
    >
      <button
        onClick={toggle}
        className="flex w-full items-center justify-between gap-2 rounded-t-xl border-b border-caramel/15 bg-gold/[0.07] px-3 py-2 text-left"
      >
        <span className="flex items-center gap-1.5">
          <Globe size={13} className="text-gold" />
          <span className="text-[11.5px] font-medium text-latte/85">Sent by country</span>
        </span>
        <span className="text-[10.5px] text-latte/45">
          {open ? `${rows.length} countries` : `${companies} companies`}
        </span>
      </button>

      {open && (
        <>
          {/* Tall enough for a dozen countries without scrolling, and
              capped against the window rather than a fixed height so it
              cannot grow past the bottom of a small screen. */}
          <div className="max-h-[65vh] overflow-y-auto px-3 py-1.5">
            {rows.map((r) => (
              <div key={r.country} className="flex items-baseline justify-between gap-2 py-[3px]">
                <span className="truncate text-[11.5px] text-latte/70">{r.country}</span>
                <span className="shrink-0 tabular-nums text-[11.5px] text-latte/90">
                  {r.companies}
                  {r.emails !== r.companies && (
                    <span className="ml-1 text-[10px] text-latte/35">({r.emails})</span>
                  )}
                </span>
              </div>
            ))}
          </div>
          <div className="rounded-b-xl border-t border-caramel/15 px-3 py-1.5 text-[10.5px] text-latte/45">
            {companies} companies · {emails} emails
            <span className="ml-1 text-latte/30">— (n) = emails, where a firm had several</span>
          </div>
        </>
      )}
    </aside>
  )
}

/** Status pill. Colour always ships with the label, never alone. */
function StatusPill({ status }: { status: OutreachStatus }) {
  const m = OUTREACH_META[status]
  return (
    <span
      className="chip"
      style={{ borderColor: `${m.hex}66`, backgroundColor: `${m.hex}1f`, color: m.hex }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: m.hex }} />
      {m.label}
    </span>
  )
}

export function Outreach() {
  const toast = useToast()
  const navigate = useNavigate()
  const [rows, setRows] = useState<Row[]>([])
  const [stats, setStats] = useState<OutreachStats | null>(null)
  const [insights, setInsights] = useState<Insights | null>(null)
  const [loading, setLoading] = useState(true)

  const [search, setSearch] = useState('')
  const [method, setMethod] = useState('')
  const [status, setStatus] = useState('')
  const [country, setCountry] = useState('')
  const [dueOnly, setDueOnly] = useState(false)
  const [period, setPeriod] = useState('')
  const [countries, setCountries] = useState<CountryOption[]>([])

  // The full record, fetched on open. The list rows do not carry the message
  // we sent or the notes — that is the point of the list being small.
  const [editing, setEditing] = useState<FullRow | null>(null)
  const [opening, setOpening] = useState<number | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState<Row | null>(null)

  const [unlogged, setUnlogged] = useState<MergeGroup[]>([])
  const [byCountry, setByCountry] = useState<CountrySent[]>([])
  const [combining, setCombining] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [list, s] = await Promise.all([
        api.listOutreach({
          search: search.trim() || undefined,
          contact_method: method || undefined,
          status: status || undefined,
          country: country || undefined,
          due: dueOnly || undefined,
          contacted_from: windowFor(period).from,
          contacted_to: windowFor(period).to,
        }),
        api.outreachStats().catch(() => null),
      ])
      setRows(list)
      setStats(s)
    } catch {
      toast.error('Could not load the outreach list.')
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, method, status, country, dueOnly, period])

  useEffect(() => {
    // Not part of `load`: these summarise the whole log, so re-fetching them
    // on every keystroke would be wasted work and would make the panels
    // flicker while you type.
    // Twenty, not the default eight. Eight was enough while the log was small;
    // with more countries than that, the tail was silently missing from the
    // one panel that is supposed to say where the prospecting has gone.
    api
      .outreachInsights(20)
      .then(setInsights)
      .catch(() => setInsights(null))
    // From the send history, so a company with two mailboxes counts once.
    api
      .sentByCountry()
      .then(setByCountry)
      .catch(() => setByCountry([]))
  }, [rows.length])

  useEffect(() => {
    const id = window.setTimeout(() => void load(), 300)
    return () => window.clearTimeout(id)
  }, [load])

  /** Whether any email went out without leaving a row in the log.
   *
   * Deliberately not part of `load`. It asks a question about the whole log
   * and cannot change from typing in the search box, so re-asking it on every
   * debounced keystroke would pay a round trip to another region for an
   * answer that had not moved.
   */
  const refreshGaps = useCallback(async () => {
    setUnlogged(await api.unloggedOutreach().catch(() => []))
  }, [])

  useEffect(() => {
    void refreshGaps()
  }, [refreshGaps])

  useEffect(() => {
    // Every country the app knows, so the picker still offers one whose only
    // rows are closed or filtered out of the current list.
    void knownCountries().then((list) => setCountries(list.filter((c) => c.prospects > 0)))
  }, [rows.length])

  /** Open one record for editing, pulling the parts the list left behind. */
  const openRecord = async (row: Row) => {
    setOpening(row.id)
    try {
      setEditing(await api.getOutreach(row.id))
    } catch {
      toast.error('Could not open that record.')
    } finally {
      setOpening(null)
    }
  }

  /** They answered. Recorded here because replies are read in Gmail. */
  const markReplied = async (row: Row) => {
    try {
      const updated = await api.updateOutreach(row.id, {
        status: 'replied',
        replied_on: new Date().toISOString().slice(0, 10),
        // Chasing somebody who has answered is the fastest way to undo a
        // reply, so the follow-up date goes with the status.
        next_follow_up: null,
        next_action: 'They replied — read it in Gmail and decide',
      })
      setRows((list) => list.map((r) => (r.id === row.id ? { ...r, ...updated } : r)))
      toast.success(`${row.company_name} marked as replied.`)
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not update that.')
    }
  }

  const markNotInterested = async (row: Row) => {
    try {
      const updated = await api.updateOutreach(row.id, {
        status: 'not_interested',
        next_follow_up: null,
        next_action: null,
      })
      setRows((list) => list.map((r) => (r.id === row.id ? { ...r, ...updated } : r)))
      toast.success(`${row.company_name} closed — no further chasing.`)
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not update that.')
    }
  }

  const followUp = async (row: Row) => {
    try {
      const updated = await api.logFollowUp(row.id)
      setRows((list) => list.map((r) => (r.id === row.id ? updated : r)))
      toast.success(`Follow-up logged. Next one ${relativeDays(updated.next_follow_up)}.`)
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not log the follow-up.')
    }
  }

  /** A prospect who answered becomes a quote on the trade desk. */
  const convert = async (row: Row) => {
    try {
      const quote = await api.convertToQuote(row.id)
      toast.success(`${quote.company_name} is now a quote.`)
      navigate(`/app/trade/quotes/${quote.id}`)
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not create the quote.')
    }
  }

  const remove = async () => {
    if (!deleting) return
    try {
      await api.deleteOutreach(deleting.id)
      setRows((list) => list.filter((r) => r.id !== deleting.id))
      toast.success('Record removed.')
    } catch {
      toast.error('Could not delete the record.')
    } finally {
      setDeleting(null)
    }
  }

  const filtered = search || method || status || country || dueOnly || period

  const relog = async () => {
    setCombining(true)
    try {
      const made = await api.relogOutreach()
      await Promise.all([load(), refreshGaps()])
      toast.success(
        `Added ${made.length} compan${made.length === 1 ? 'y' : 'ies'} back to the log.`,
      )
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not rebuild the rows.')
    } finally {
      setCombining(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl text-latte">Outreach</h1>
          <p className="mt-1 text-sm text-latte/50">
            {loading
              ? 'Loading…'
              : filtered
                ? `${rows.length} row${rows.length === 1 ? '' : 's'} matching your filters`
                : /* Companies and mailboxes are different numbers and both are
                     true. Saying "175 companies" over 161 of them, because two
                     addresses at one firm are two rows, is the kind of wrong
                     that gets repeated in a meeting. */
                  `${stats?.companies ?? rows.length} companies · ${stats?.total ?? rows.length} mailboxes`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* Emailed, but with no row in the log. The send history is kept
              separately and cannot be deleted, so a gap between the two is
              both detectable and repairable — and a company that was written
              to while appearing untouched is the worst state to leave. */}
          {unlogged.length > 0 && (
            <Button onClick={relog} disabled={combining} icon={<FilePlus2 size={16} />}>
              Add {unlogged.length} missing to the log
            </Button>
          )}
          <Button onClick={() => setCreating(true)} icon={<Plus size={16} />}>
            Log Outreach
          </Button>
        </div>
      </div>

      <CountryNote rows={byCountry} />

      {/* Four numbers, not a dashboard. */}
      {stats && stats.total > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Tracked" value={stats.total} />
          <Stat label="Awaiting reply" value={stats.awaiting_reply} />
          <Stat label="Replied" value={stats.replied} accent="#4FD18B" />
          <Stat
            label="Due now"
            value={stats.due_today + stats.overdue}
            accent={stats.due_today + stats.overdue > 0 ? '#E0A458' : undefined}
          />
        </div>
      )}

      {stats && stats.total > 0 && (
        <OutreachInsights
          data={insights}
          loading={loading && !insights}
          active={country}
          onPick={(label) => setCountry((cur) => (cur === label ? '' : label))}
        />
      )}

      <Card className="!p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="relative">
            <Search
              size={15}
              className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-latte/35"
            />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search company, person, website, notes…"
              className="pl-10"
              aria-label="Search outreach"
            />
          </div>
          <Select
            value={method}
            onChange={(e) => setMethod(e.target.value)}
            aria-label="Filter by contact method"
            options={[
              { value: '', label: 'All channels' },
              ...METHOD_ORDER.map((m) => ({ value: m, label: METHOD_META[m].label })),
            ]}
          />
          <Select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            aria-label="Filter by status"
            options={[
              { value: '', label: 'All statuses' },
              ...OUTREACH_ORDER.map((s) => ({ value: s, label: outreachLabel(s) })),
            ]}
          />
          {/* When they were contacted. Presets first, because "this month"
              is asked far more often than any particular month, then every
              month and year that actually holds rows — offering an empty
              December would be offering a dead end. */}
          <Select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            aria-label="Filter by when they were contacted"
            options={[
              { value: '', label: 'Any time' },
              { value: 'today', label: 'Today' },
              { value: 'last7', label: 'Last 7 days' },
              { value: 'last30', label: 'Last 30 days' },
              { value: 'thismonth', label: 'This month' },
              { value: 'lastmonth', label: 'Last month' },
              ...(stats?.months ?? []).map((m) => ({
                value: m.value,
                label: `${m.label} · ${m.count}`,
              })),
              ...(stats?.years ?? []).map((y) => ({
                value: y.value,
                label: `All of ${y.label} · ${y.count}`,
              })),
            ]}
          />
          <Select
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            aria-label="Filter by country"
            options={[
              { value: '', label: 'All countries' },
              ...countries.map((c) => ({ value: c.name, label: `${c.name} · ${c.prospects}` })),
            ]}
          />
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-4">
          <label className="flex cursor-pointer items-center gap-2 text-xs text-latte/55">
            <input
              type="checkbox"
              checked={dueOnly}
              onChange={(e) => setDueOnly(e.target.checked)}
              className="h-4 w-4 accent-[#D9A05B]"
            />
            Only show follow-ups that are due
          </label>
          {filtered && (
            <button
              onClick={() => {
                setSearch('')
                setMethod('')
                setStatus('')
                setCountry('')
                setDueOnly(false)
                setPeriod('')
              }}
              className="text-xs text-gold hover:underline"
            >
              Clear filters
            </button>
          )}
        </div>
      </Card>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          emoji="📮"
          title={filtered ? 'Nothing matches those filters' : 'No outreach logged yet'}
          hint={
            filtered
              ? 'Try widening the search.'
              : 'Record the first roaster you contacted — where you found them, what you sent, and when to chase.'
          }
          action={
            filtered ? undefined : (
              <Button onClick={() => setCreating(true)} icon={<Plus size={16} />}>
                Log Outreach
              </Button>
            )
          }
        />
      ) : (
        <div className="space-y-3">
          {rows.map((r) => {
            const overdue =
              r.next_follow_up &&
              new Date(r.next_follow_up) <= new Date(new Date().toDateString()) &&
              r.status !== 'no_response' &&
              r.status !== 'not_interested'
            return (
              <Card key={r.id} className="!p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <button
                    onClick={() => void openRecord(r)}
                    className="min-w-0 flex-1 text-left"
                    aria-label={`Open ${r.company_name}`}
                    aria-busy={opening === r.id}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium text-latte">{r.company_name}</span>
                      {r.contact_person && (
                        <span className="text-[11px] text-latte/45">· {r.contact_person}</span>
                      )}
                      {r.country && <span className="text-[11px] text-latte/35">{r.country}</span>}
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <StatusPill status={r.status} />
                      {/* The address, not the word "Email".
                          One company with three mailboxes is three rows here,
                          on purpose — each is written to and answers (or does
                          not) separately. Labelling every row "Email" made
                          those three look like the same row entered thrice. */}
                      <span className="chip max-w-full border-caramel/25 bg-bean/40 text-latte/55">
                        {METHOD_META[r.contact_method].icon}{' '}
                        <span className="truncate">
                          {r.contact_point || r.email || METHOD_META[r.contact_method].label}
                        </span>
                      </span>
                      {r.follow_ups_sent > 0 && (
                        <span className="text-[11px] text-latte/40">
                          {r.follow_ups_sent} follow-up{r.follow_ups_sent === 1 ? '' : 's'}
                        </span>
                      )}
                    </div>
                    {r.their_reply && (
                      <p className="mt-2 line-clamp-2 rounded-lg border border-emerald-400/20 bg-emerald-400/[0.06] px-3 py-2 text-[12px] leading-relaxed text-latte/75">
                        {r.their_reply}
                      </p>
                    )}
                    {r.next_action && (
                      <p className="mt-2 text-[12px] text-gold/85">→ {r.next_action}</p>
                    )}
                    <p className="mt-2 text-[11px] text-latte/35">
                      {r.contacted_on ? `Contacted ${formatDate(r.contacted_on)}` : 'Not yet sent'}
                      {r.next_follow_up && (
                        <>
                          {' · '}
                          <span className={overdue ? 'text-gold' : ''}>
                            next {relativeDays(r.next_follow_up)}
                          </span>
                        </>
                      )}
                    </p>
                  </button>

                  <div className="flex shrink-0 items-center gap-1">
                    {r.website && (
                      <a
                        href={r.website.startsWith('http') ? r.website : `https://${r.website}`}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-lg p-2 text-latte/40 transition hover:bg-latte/10 hover:text-gold"
                        aria-label={`Open ${r.company_name} website`}
                      >
                        <Globe size={15} />
                      </a>
                    )}
                    {r.status !== 'replied' && (
                      <button
                        onClick={() => markReplied(r)}
                        className="rounded-lg p-2 text-latte/40 transition hover:bg-emerald-400/15 hover:text-emerald-300"
                        aria-label={`Mark ${r.company_name} as replied`}
                        title="They answered — stop chasing them"
                      >
                        <MailCheck size={15} />
                      </button>
                    )}
                    {r.status !== 'not_interested' && r.status !== 'replied' && (
                      <button
                        onClick={() => markNotInterested(r)}
                        className="rounded-lg p-2 text-latte/40 transition hover:bg-latte/10 hover:text-latte/70"
                        aria-label={`Close ${r.company_name} as not interested`}
                        title="Not interested — close it"
                      >
                        <CircleSlash size={15} />
                      </button>
                    )}
                    <button
                      onClick={() => followUp(r)}
                      className="rounded-lg p-2 text-latte/40 transition hover:bg-gold/15 hover:text-gold"
                      aria-label={`Log a follow-up for ${r.company_name}`}
                      title="I chased them again today"
                    >
                      <Clock size={15} />
                    </button>
                    {r.quote_id ? (
                      <button
                        onClick={() => navigate(`/app/trade/quotes/${r.quote_id}`)}
                        className="rounded-lg p-2 text-gold/70 transition hover:bg-gold/15 hover:text-gold"
                        aria-label={`Open the quote for ${r.company_name}`}
                        title="Open its quote on the trade desk"
                      >
                        <FilePlus2 size={15} />
                      </button>
                    ) : (
                      <button
                        onClick={() => convert(r)}
                        className="rounded-lg p-2 text-latte/40 transition hover:bg-gold/15 hover:text-gold"
                        aria-label={`Turn ${r.company_name} into a quote`}
                        title="Turn into a quote on the trade desk"
                      >
                        <FilePlus2 size={15} />
                      </button>
                    )}
                    <button
                      onClick={() => setDeleting(r)}
                      className="rounded-lg p-2 text-latte/40 transition hover:bg-red-500/15 hover:text-red-300"
                      aria-label={`Delete ${r.company_name}`}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      <OutreachModal
        open={creating || !!editing}
        row={editing}
        onClose={() => {
          setCreating(false)
          setEditing(null)
        }}
        onSaved={() => {
          setCreating(false)
          setEditing(null)
          void load()
        }}
      />

      <ConfirmDialog
        open={!!deleting}
        title="Delete this record?"
        message={`Everything recorded about ${deleting?.company_name} will be permanently removed.`}
        onConfirm={remove}
        onCancel={() => setDeleting(null)}
      />
    </div>
  )
}

function Stat({ label, value, accent }: { label: string; value: number; accent?: string }) {
  return (
    <div className="rounded-xl border border-caramel/15 bg-espresso/40 px-4 py-3">
      <p className="font-body text-2xl font-semibold" style={{ color: accent ?? undefined }}>
        {value}
      </p>
      <p className="mt-0.5 text-[11px] uppercase tracking-wider text-latte/45">{label}</p>
    </div>
  )
}

/* ─────────────────────────────────────────────────────────────── the form */

const EMPTY = {
  company_name: '',
  contact_person: '',
  website: '',
  email: '',
  country: '',
  contact_method: 'email' as ContactMethod,
  contact_point: '',
  contacted_on: '',
  message_sent: '',
  status: 'follow_up_needed' as OutreachStatus,
  their_reply: '',
  replied_on: '',
  next_action: '',
  next_follow_up: '',
  notes: '',
}

function OutreachModal({
  open,
  row,
  onClose,
  onSaved,
}: {
  open: boolean
  row: FullRow | null
  onClose: () => void
  onSaved: () => void
}) {
  const toast = useToast()
  const [form, setForm] = useState(EMPTY)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const str = (v: string | null | undefined) => v ?? ''
    setForm(
      row
        ? {
            company_name: str(row.company_name),
            contact_person: str(row.contact_person),
            website: str(row.website),
            email: str(row.email),
            country: str(row.country),
            contact_method: row.contact_method,
            contact_point: str(row.contact_point),
            contacted_on: str(row.contacted_on),
            message_sent: str(row.message_sent),
            status: row.status,
            their_reply: str(row.their_reply),
            replied_on: str(row.replied_on),
            next_action: str(row.next_action),
            next_follow_up: str(row.next_follow_up),
            notes: str(row.notes),
          }
        : EMPTY,
    )
  }, [row, open])

  const set = (k: keyof typeof EMPTY) => (v: string) => setForm((f) => ({ ...f, [k]: v }))
  const text = (v: string) => (v.trim() ? v.trim() : null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    const payload: Record<string, unknown> = {
      company_name: text(form.company_name),
      contact_person: text(form.contact_person),
      website: text(form.website),
      email: text(form.email),
      country: text(form.country),
      contact_method: form.contact_method,
      contact_point: text(form.contact_point),
      contacted_on: form.contacted_on || null,
      message_sent: text(form.message_sent),
      status: form.status,
      their_reply: text(form.their_reply),
      replied_on: form.replied_on || null,
      next_action: text(form.next_action),
      next_follow_up: form.next_follow_up || null,
      notes: text(form.notes),
    }
    try {
      if (row) await api.updateOutreach(row.id, payload)
      else await api.createOutreach(payload)
      // A country typed here belongs in the next form's suggestions.
      forgetCountries()
      toast.success(row ? 'Record updated.' : '📮 Outreach logged.')
      onSaved()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not save the record.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={row ? row.company_name : 'Log Outreach'}
      subtitle="Nothing is required — save whatever you have"
      width="max-w-3xl"
    >
      <form onSubmit={submit} noValidate className="space-y-5">
        {/* who */}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Company">
            <Input
              value={form.company_name}
              onChange={(e) => set('company_name')(e.target.value)}
              placeholder="Oslo Specialty Roastery"
            />
          </Field>
          <Field label="Contact person">
            <Input
              value={form.contact_person}
              onChange={(e) => set('contact_person')(e.target.value)}
              placeholder="Ingrid"
            />
          </Field>
          <Field label="Website">
            <Input
              value={form.website}
              onChange={(e) => set('website')(e.target.value)}
              placeholder="oslospecialty.no"
            />
          </Field>
          <Field label="Country">
            <CountryInput value={form.country} onChange={set('country')} placeholder="Norway" />
          </Field>
        </div>

        {/* where we contacted them */}
        <div className="rounded-xl border border-caramel/15 bg-bean/25 p-4">
          <p className="mb-3 text-[11px] uppercase tracking-wider text-gold/70">
            Where we contacted them
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Channel">
              <Select
                value={form.contact_method}
                onChange={(e) => set('contact_method')(e.target.value)}
                options={METHOD_ORDER.map((m) => ({
                  value: m,
                  label: `${METHOD_META[m].icon}  ${METHOD_META[m].label}`,
                }))}
              />
            </Field>
            <Field
              label="Exact place"
              hint="The LinkedIn URL, the contact-form page, the inbox"
            >
              <Input
                value={form.contact_point}
                onChange={(e) => set('contact_point')(e.target.value)}
                placeholder="oslospecialty.no/contact"
              />
            </Field>
            <Field label="Email (if they have one)">
              <Input
                value={form.email}
                onChange={(e) => set('email')(e.target.value)}
                placeholder="—"
              />
            </Field>
            <Field label="Date contacted">
              <Input
                type="date"
                value={form.contacted_on}
                onChange={(e) => set('contacted_on')(e.target.value)}
              />
            </Field>
          </div>
        </div>

        {/* what we sent */}
        <Field label="Message we sent">
          <Textarea
            rows={5}
            value={form.message_sent}
            onChange={(e) => set('message_sent')(e.target.value)}
            placeholder="Paste what you sent."
          />
        </Field>

        {/* what came back */}
        <div className="rounded-xl border border-caramel/15 bg-bean/25 p-4">
          <p className="mb-3 text-[11px] uppercase tracking-wider text-gold/70">What came back</p>

          <Field label="Their reply" className="mb-4">
            <Textarea
              rows={4}
              value={form.their_reply}
              onChange={(e) => set('their_reply')(e.target.value)}
              placeholder="Paste exactly what they wrote back."
            />
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Status">
              <Select
                value={form.status}
                onChange={(e) => set('status')(e.target.value)}
                options={OUTREACH_ORDER.map((s) => ({ value: s, label: outreachLabel(s) }))}
              />
            </Field>
            <Field label="Date they replied">
              <Input
                type="date"
                value={form.replied_on}
                onChange={(e) => set('replied_on')(e.target.value)}
              />
            </Field>
          </div>
        </div>

        {/* what next */}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Our next action">
            <Input
              value={form.next_action}
              onChange={(e) => set('next_action')(e.target.value)}
              placeholder="Send FOB pricing and a sample"
            />
          </Field>
          <Field label="Next follow-up date">
            <Input
              type="date"
              value={form.next_follow_up}
              onChange={(e) => set('next_follow_up')(e.target.value)}
            />
          </Field>
        </div>

        <Field label="Notes / memory" hint="Anything worth remembering next time you talk">
          <Textarea
            rows={3}
            value={form.notes}
            onChange={(e) => set('notes')(e.target.value)}
            placeholder="No email or LinkedIn published. Small-batch roaster, around 200 kg a month. Asked to be contacted after harvest."
          />
        </Field>

        <div className="flex justify-end gap-3 border-t border-caramel/15 pt-4">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={busy} icon={<Send size={14} />}>
            {row ? 'Save changes' : 'Log outreach'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
