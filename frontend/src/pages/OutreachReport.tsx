/**
 * What was sent, on which day, and what was not sent and why.
 *
 * Read from a ledger that no delete touches. A campaign is a working file:
 * once it is finished, or once it was only a test, it gets thrown away — and
 * with the old design the day's history went with it, so the app forgot it had
 * written to those companies this morning. This page is the memory that
 * outlives the campaign.
 */
import {
  CalendarDays,
  Copy,
  Inbox,
  Mailbox,
  Play,
  RefreshCw,
  Square,
  RotateCcw,
  SkipForward,
  Trash2,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  BarTable,
  ChartFrame,
  ColumnChart,
  ColumnTable,
  FunnelChart,
  FunnelTable,
  Heatmap,
  HeatmapTable,
  LegendItem,
  RoastBarChart,
  TrendChart,
  TrendTable,
} from '../components/charts'
import { Button, Card, ConfirmDialog, EmptyState, Select, Skeleton } from '../components/ui'
import { PaginatedList } from '../components/PaginatedList'
import { ApiError, api } from '../lib/api'
import { formatDateTime } from '../lib/format'
import { useToast } from '../lib/toast'
import type {
  Campaign,
  DailyReport,
  DuplicateGroup,
  InboundReply,
  TrendReport,
} from '../lib/types'
import { CATEGORICAL } from '../lib/viz'

/** The charts, all of them about cold outreach.
 *
 * They were on the trade-desk dashboard, which was the wrong room: that page
 * answers questions about quotes, orders and open value, and "how many emails
 * went out on Tuesday" is not one of them. Somebody asking these is already
 * here.
 */
const CHARTS = [
  { value: '', label: 'Day-by-day log' },
  { value: 'funnel', label: 'Conversion funnel' },
  { value: 'volume', label: 'Emails sent per day' },
  { value: 'replies', label: 'Sent vs replied, by month' },
  { value: 'countries', label: 'Countries by month' },
  { value: 'speed', label: 'How fast people reply' },
]

const OUTCOME_TONE: Record<string, string> = {
  duplicate: 'text-latte/55',
  skipped: 'text-latte/55',
  failed: 'text-red-300',
}

export function OutreachReport() {
  const toast = useToast()
  const [report, setReport] = useState<DailyReport | null>(null)
  const [dupes, setDupes] = useState<DuplicateGroup[]>([])
  const [binned, setBinned] = useState<Campaign[]>([])
  const [loading, setLoading] = useState(true)
  const [purging, setPurging] = useState<Campaign | null>(null)
  const [chart, setChart] = useState('')
  const [trends, setTrends] = useState<TrendReport | null>(null)
  const [funnel, setFunnel] = useState<{ stage: string; count: number }[]>([])
  const [replies, setReplies] = useState<InboundReply[]>([])

  const load = useCallback(async () => {
    try {
      const [r, d, b, t, dash, inbox] = await Promise.all([
        api.dailyReport(60),
        api.duplicateReport().catch(() => []),
        api.listCampaigns(true).catch(() => []),
        api.trendReport(12).catch(() => null),
        // The funnel lives on the dashboard payload because it spans both
        // sides of the business; this page only borrows it.
        api.dashboard().catch(() => null),
        api.listReplies().catch(() => []),
      ])
      setReport(r)
      setDupes(d)
      setBinned(b)
      setTrends(t)
      setFunnel(dash?.funnel ?? [])
      setReplies(inbox)
    } catch {
      toast.error('Could not load the report.')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    void load()
  }, [load])

  const restore = async (c: Campaign) => {
    try {
      await api.restoreCampaign(c.id)
      toast.success(`${c.name} is back, paused.`)
      await load()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not restore it.')
    }
  }

  const purge = async () => {
    if (!purging) return
    try {
      await api.purgeCampaign(purging.id)
      toast.success('Deleted for good. The send history is still in this report.')
      await load()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not delete it.')
    } finally {
      setPurging(null)
    }
  }

  if (loading) return <Skeleton className="h-96" />

  const t = report?.totals

  const funnelSteps = funnel.map((f) => ({ label: String(f.stage), value: Number(f.count) || 0 }))

  // The ledger's days arrive newest first; a time axis reads the other way.
  const volumeColumns = [...(report?.days ?? [])].reverse().map((d) => ({
    label: new Date(d.day).toLocaleDateString(undefined, { day: '2-digit', month: 'short' }),
    value: d.sent,
    meta: [
      d.failed ? `${d.failed} failed` : null,
      d.duplicates ? `${d.duplicates} already contacted` : null,
    ]
      .filter(Boolean)
      .join(' · '),
  }))

  const replySeries = [
    {
      name: 'Sent',
      values: (trends?.by_month ?? []).map((m) => m.sent),
      color: CATEGORICAL[0],
    },
    {
      name: 'Replied',
      values: (trends?.by_month ?? []).map((m) => m.replied),
      color: CATEGORICAL[2],
    },
  ]

  const speedBars = (trends?.response_days ?? []).map((b) => ({
    label: b.bucket,
    value: b.count,
  }))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl text-latte">Outreach Report</h1>
        <p className="mt-1 text-sm text-latte/50">
          Every email the agent has sent, by day. Kept even when the campaign that sent it is
          deleted.
        </p>
      </div>

      {/* --------------------------------------------------------- totals */}
      {t && (
        <Card>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            <Figure label="Sent, all time" value={t.sent} tone="text-emerald-300" />
            <Figure label="Companies reached" value={t.companies} />
            <Figure label="Already contacted" value={t.duplicates} />
            <Figure label="Skipped" value={t.skipped} />
            <Figure
              label="Failed"
              value={t.failed}
              tone={t.failed ? 'text-red-300' : undefined}
            />
          </div>
          <p className="mt-4 rounded-lg border border-caramel/20 bg-bean/30 px-3.5 py-2.5 text-[12px] text-latte/65">
            Today: <span className="text-latte">{t.today.sent}</span> of {t.today.limit} sent,{' '}
            {t.today.remaining} still available.
          </p>
        </Card>
      )}

      {/* ------------------------------------------------------- charts */}
      <Card className="!p-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-[11px] uppercase tracking-wider text-latte/45">Show</span>
          <div className="min-w-[240px]">
            <Select
              value={chart}
              onChange={(e) => setChart(e.target.value)}
              aria-label="Which chart to show"
              options={CHARTS}
            />
          </div>
        </div>
      </Card>

      {chart === 'funnel' && (
        <ChartFrame
          title="From cold list to completed order"
          subtitle="Each step is a subset of the one above it, so the drop between them is real"
          table={<FunnelTable steps={funnelSteps} />}
        >
          <FunnelChart steps={funnelSteps} unit="companies" />
        </ChartFrame>
      )}

      {chart === 'volume' && (
        <ChartFrame
          title="Emails sent each day"
          subtitle={`${t?.sent ?? 0} sent in total · the dashed line is the daily ceiling`}
          table={<ColumnTable data={volumeColumns} unit="Emails" />}
        >
          <ColumnChart
            data={volumeColumns}
            limit={t?.today.limit ?? 50}
            limitLabel="a day"
            unit="emails"
          />
        </ChartFrame>
      )}

      {chart === 'replies' && (
        <ChartFrame
          title="Sent and replied, by month"
          subtitle="Both are counts of emails, so they share one axis — a second scale would let one of them lie"
          legend={
            <>
              <LegendItem color={CATEGORICAL[0]} label="Sent" />
              <LegendItem color={CATEGORICAL[2]} label="Replied" />
            </>
          }
          table={<TrendTable labels={trends?.months ?? []} series={replySeries} />}
        >
          <TrendChart labels={trends?.months ?? []} series={replySeries} />
        </ChartFrame>
      )}

      {chart === 'countries' && (
        <ChartFrame
          title="Where the emails went, month by month"
          subtitle="Darker is more. A grid rather than a stack, because thirteen countries would need thirteen colours"
          table={
            <HeatmapTable
              rows={(trends?.country_by_month ?? []).map((c) => ({
                label: c.country,
                cells: c.cells,
              }))}
              columns={trends?.months ?? []}
            />
          }
        >
          <Heatmap
            rows={(trends?.country_by_month ?? []).map((c) => ({
              label: c.country,
              cells: c.cells,
            }))}
            columns={trends?.months ?? []}
            unit="emails"
          />
        </ChartFrame>
      )}

      {chart === 'speed' && (
        <ChartFrame
          title="How long people take to reply"
          subtitle={
            trends?.replies_counted
              ? `${trends.replies_counted} repl${trends.replies_counted === 1 ? 'y' : 'ies'} — only the ones who answered are counted`
              : 'Nobody has been marked as replied yet, so there is nothing to measure'
          }
          table={<BarTable data={speedBars} unit="Replies" />}
        >
          <RoastBarChart data={speedBars} unit="replies" />
        </ChartFrame>
      )}

      {/* ------------------------------------------------------- what came back */}
      {replies.length > 0 && <RepliesReceived replies={replies} onChanged={load} />}

      {/* ------------------------------------------------ what was skipped */}
      {report && <NotWrittenTo report={report} />}

      {/* ------------------------------------------------ same name report */}
      {dupes.length > 0 && (
        <Card>
          <div className="mb-3 flex items-center gap-2.5">
            <Copy size={17} className="text-gold" />
            <div>
              <h2 className="font-display text-lg text-latte">Same name, different company</h2>
              <p className="text-[11px] text-latte/45">
                {dupes.length} potential duplicate{dupes.length === 1 ? '' : 's'}. Each was written to separately, because the address and mailbox differ. Worth a
                look in case any pair is really one business.
              </p>
            </div>
          </div>
          <PaginatedList
            items={dupes}
            initialCount={8}
            increment={8}
            containerClassName="space-y-3"
            buttonContainerClassName="flex justify-center border-t border-caramel/15 pt-4"
          >
            {(visibleDupes) => (
              <>
                {visibleDupes.map((g) => (
                  <div key={g.name} className="rounded-xl border border-caramel/15 bg-bean/25 p-3.5">
                    <p className="text-sm text-latte">
                      {g.name}
                      <span className="ml-2 text-[11px] text-latte/45">
                        differs by {g.differs_by.join(', ')}
                      </span>
                    </p>
                    <div className="mt-1.5 space-y-1 text-[11.5px] text-latte/55">
                      {g.emails.map((e, i) => (
                        <p key={e}>
                          {e}
                          {g.locations[i] ? ` — ${g.locations[i]}` : ''}
                        </p>
                      ))}
                    </div>
                    <p className="mt-1.5 text-[11px] text-latte/35">
                      {g.contacted} contacted
                      {g.skipped_as_duplicate > 0 &&
                        ` · ${g.skipped_as_duplicate} skipped as already contacted`}
                    </p>
                  </div>
                ))}
              </>
            )}
          </PaginatedList>
        </Card>
      )}

      {/* ----------------------------------------------------------- days */}
      {chart !== '' ? null : !report?.days.length ? (
        <EmptyState
          emoji="📭"
          title="Nothing sent yet"
          hint="Once the agent sends its first email, every day appears here with what went out and what did not."
        />
      ) : (
        <PaginatedList
          items={report.days}
          initialCount={10}
          increment={10}
          containerClassName="space-y-4"
          buttonContainerClassName="flex justify-center border-t border-caramel/15 pt-4"
        >
          {(visibleDays) => (
            <>
              {visibleDays.map((day) => (
            <Card key={day.day}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <CalendarDays size={16} className="text-gold" />
                  <h3 className="font-display text-lg text-latte">
                    {new Date(day.day).toLocaleDateString(undefined, {
                      weekday: 'long',
                      day: 'numeric',
                      month: 'long',
                      year: 'numeric',
                    })}
                  </h3>
                </div>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-latte/55">
                  <span className="text-emerald-300">{day.sent} sent</span>
                  <span>to {day.companies} companies</span>
                  {day.duplicates > 0 && <span>{day.duplicates} already contacted</span>}
                  {day.skipped > 0 && <span>{day.skipped} skipped</span>}
                  {day.failed > 0 && <span className="text-red-300">{day.failed} failed</span>}
                  <span className="text-latte/35">
                    {day.sent}/{day.limit} of the daily limit
                  </span>
                </div>
              </div>

              {day.campaigns.length > 0 && (
                <p className="mt-1 text-[11px] text-latte/35">
                  from {day.campaigns.join(', ')}
                </p>
              )}

              {day.sent_to.length > 0 && (
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full text-[12px]">
                    <tbody>
                      {day.sent_to.map((x, i) => (
                        <tr key={`${x.email}-${i}`} className="border-t border-caramel/8">
                          <td className="py-1.5 pr-3 text-latte/80">{x.company}</td>
                          <td className="py-1.5 pr-3 text-latte/50">{x.email}</td>
                          <td className="py-1.5 pr-3 text-latte/35">{x.country}</td>
                          <td className="py-1.5 text-right text-latte/35">
                            {formatDateTime(x.at)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {day.not_sent.length > 0 && (
                <div className="mt-3 rounded-lg border border-caramel/15 bg-bean/25 p-3">
                  <p className="mb-1.5 text-[11px] uppercase tracking-wider text-latte/40">
                    Not written to
                  </p>
                  <ul className="space-y-1 text-[11.5px]">
                    {day.not_sent.map((x, i) => (
                      <li key={`${x.email}-${i}`} className={OUTCOME_TONE[x.outcome] ?? ''}>
                        <span className="text-latte/75">{x.company}</span>
                        {x.email ? ` (${x.email})` : ''} — {x.reason ?? x.outcome}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </Card>
              ))}
            </>
          )}
        </PaginatedList>
      )}

      {/* --------------------------------------------------- recycle bin */}
      <Card>
        <div className="mb-3 flex items-center gap-2.5">
          <Inbox size={17} className="text-latte/50" />
          <div>
            <h2 className="font-display text-lg text-latte">Recycle bin</h2>
            <p className="text-[11px] text-latte/45">
              {binned.length > 0 ? `${binned.length} deleted campaign${binned.length === 1 ? '' : 's'}. ` : ''}
              The emails they sent stay in the report above, whatever happens
              here.
            </p>
          </div>
        </div>
        {binned.length === 0 ? (
          <p className="py-4 text-center text-sm text-latte/35">Nothing deleted.</p>
        ) : (
          <PaginatedList
            items={binned}
            initialCount={8}
            increment={8}
            containerClassName="space-y-2"
            buttonContainerClassName="flex justify-center border-t border-caramel/15 pt-4"
          >
            {(visibleBinned) => (
              <>
                {visibleBinned.map((c) => (
              <div
                key={c.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-caramel/12 bg-bean/25 px-3.5 py-2.5"
              >
                <div>
                  <p className="text-sm text-latte/80">{c.name}</p>
                  <p className="text-[11px] text-latte/35">
                    {c.source_filename ?? 'uploaded list'} · {c.status}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    onClick={() => restore(c)}
                    icon={<RotateCcw size={14} />}
                    className="px-3 py-1.5 text-xs"
                  >
                    Restore
                  </Button>
                  <button
                    onClick={() => setPurging(c)}
                    aria-label={`Delete ${c.name} permanently`}
                    title="Delete permanently"
                    className="rounded-lg p-2 text-latte/35 transition hover:bg-red-500/15 hover:text-red-300"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
                ))}
              </>
            )}
          </PaginatedList>
        )}
      </Card>

      <ConfirmDialog
        open={!!purging}
        title={`Delete “${purging?.name}” permanently?`}
        message={
          'The queue and the drafts are destroyed and cannot be recovered. ' +
          'The record of emails it actually sent stays in this report — that history is what ' +
          'stops those companies being written to a second time.'
        }
        onConfirm={purge}
        onCancel={() => setPurging(null)}
      />
    </div>
  )
}

/* --------------------------------------------------------------- replies in */

const CLASS_LABEL: Record<string, string> = {
  interested: 'Interested',
  pricing_request: 'Wants pricing',
  sample_request: 'Wants samples',
  specification_request: 'Wants specifications',
  purchasing_contact: 'Passed to purchasing',
  needs_follow_up: 'Needs a follow-up',
  not_interested: 'Not interested',
  out_of_office: 'Out of office',
  unsubscribe: 'Asked to be removed',
  bounced: 'Bounced',
  other: 'Other',
}

/** The messages that came back, and which company each belongs to.
 *
 * Matched replies have already changed their outreach record — this is a
 * reading view, not a queue. The one thing it asks of a person is the
 * unmatched ones: the app will not guess which company a stranger belongs to,
 * because filing a reply against the wrong company is worse than filing it
 * against none.
 *
 * There is no reply box. Answering happens in Gmail, in the thread the
 * customer already has open.
 */
function RepliesReceived({
  replies,
  onChanged,
}: {
  replies: InboundReply[]
  onChanged: () => Promise<void>
}) {
  const toast = useToast()
  const [showHandled, setShowHandled] = useState(false)
  const [checking, setChecking] = useState(false)
  // Reading on a repeat, for as long as this page is open and the switch is
  // on. Deliberately here rather than on the server: a background reader is a
  // database query every minute whether or not anybody is there, and that is
  // what exhausted the database's allowance once already. Started from a page,
  // it cannot outlive the tab.
  const [reading, setReading] = useState(false)
  const [reads, setReads] = useState(0)
  const visible = showHandled ? replies : replies.filter((r) => !r.handled)

  const readInbox = useCallback(async () => {
    const r = await api.checkReplies()
    setReads((n) => n + 1)
    if (r.error) throw new Error(r.error)
    if (r.stored) {
      toast.success(
        `${r.stored} new: ${r.matched} matched to a company, ${r.unmatched} need a look.`,
      )
      await onChanged()
    }
    return r
  }, [onChanged, toast])

  const checkNow = async () => {
    setChecking(true)
    try {
      const r = await readInbox()
      if (!r.stored) toast.success(`Read ${r.checked} messages — nothing new.`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not read the mailbox.')
    } finally {
      setChecking(false)
    }
  }

  useEffect(() => {
    if (!reading) return
    let stopped = false
    const once = async () => {
      try {
        await readInbox()
      } catch (err) {
        if (stopped) return
        toast.error(err instanceof Error ? err.message : 'Could not read the mailbox.')
        setReading(false)
      }
    }
    void once()
    const timer = window.setInterval(() => void once(), 60_000)
    return () => {
      stopped = true
      window.clearInterval(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reading])
  const ignore = async (r: InboundReply) => {
    try {
      await api.markReplyHandled(r.id, true)
      await onChanged()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not update it.')
    }
  }

  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <Mailbox size={17} className="text-gold" />
          <div>
            <h2 className="font-display text-lg text-latte">What came back</h2>
            <p className="text-[11px] text-latte/45">
              Replies to the outreach you sent. Nothing is read on a timer — press a
              button below.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="ghost" onClick={checkNow} disabled={checking || reading}>
            <RefreshCw size={14} className={checking ? 'animate-spin' : undefined} />
            {checking ? 'Reading…' : 'Check now'}
          </Button>
          {/* Keeps reading once a minute until stopped. Closing this page stops
              it too — nothing carries on server-side. */}
          <Button
            variant={reading ? 'primary' : 'ghost'}
            onClick={() => {
              setReads(0)
              setReading((v) => !v)
            }}
          >
            {reading ? (
              <>
                <Square size={13} /> Stop reading
              </>
            ) : (
              <>
                <Play size={13} /> Start reading
              </>
            )}
          </Button>
          <Button variant="ghost" onClick={() => setShowHandled((v) => !v)}>
            {showHandled ? 'Hide dealt-with' : 'Show all'}
          </Button>
        </div>
      </div>

      {reading && (
        <p className="mb-3 rounded-lg border border-emerald-400/25 bg-emerald-400/[0.07] px-3 py-2 text-[11.5px] text-emerald-300/90">
          Reading the inbox every minute — checked {reads} time{reads === 1 ? '' : 's'}. This runs
          only while the page is open; closing the tab stops it.
        </p>
      )}

      {visible.length === 0 ? (
        <EmptyState
          emoji="📬"
          title="Nothing waiting"
          hint="Every reply that arrived has been dealt with."
        />
      ) : (
        <PaginatedList
          items={visible}
          initialCount={8}
          increment={8}
          containerClassName="space-y-4"
          buttonContainerClassName="flex justify-center border-t border-caramel/15 pt-4"
        >
          {(visibleReplies) => (
            <>
              {visibleReplies.map((r) => (
            <div
              key={r.id}
              className="rounded-lg border border-caramel/20 bg-bean/30 px-3.5 py-3"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <span className="text-sm font-medium text-latte">
                  {r.company_name ?? r.from_name ?? r.from_email ?? 'Unknown sender'}
                </span>
                <span className="text-[11px] text-latte/40">
                  {formatDateTime(r.received_at)}
                  {r.reply_speed_hours != null &&
                    ` · answered in ${
                      r.reply_speed_hours < 48
                        ? `${Math.round(r.reply_speed_hours)}h`
                        : `${Math.round(r.reply_speed_hours / 24)} days`
                    }`}
                </span>
              </div>

              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                <span className="chip border-caramel/30 bg-bean/50 text-latte/70">
                  {CLASS_LABEL[r.classification] ?? r.classification}
                </span>
                {r.match_kind === 'unmatched' ? (
                  <span className="chip border-amber-400/40 bg-amber-400/10 text-amber-300">
                    Not matched to a company
                  </span>
                ) : (
                  <span className="chip border-emerald-400/30 bg-emerald-400/10 text-emerald-300/90">
                    {r.match_kind === 'thread'
                      ? 'Matched by the email thread'
                      : r.match_kind === 'address'
                        ? 'Matched by sender address'
                        : 'Matched by hand'}
                  </span>
                )}
                {r.from_email && (
                  <span className="text-[11px] text-latte/35">{r.from_email}</span>
                )}
              </div>

              {r.suggested_reply && (
                <p className="mt-2 text-[12.5px] leading-relaxed text-latte/80">
                  {r.suggested_reply}
                </p>
              )}

              {r.body && (
                <p className="mt-2 whitespace-pre-wrap break-words text-[12px] leading-relaxed text-latte/60">
                  {r.body.length > 400 ? `${r.body.slice(0, 400)}…` : r.body}
                </p>
              )}

              <div className="mt-2.5 flex flex-wrap items-center gap-2">
                {r.outreach_id && (
                  <Link
                    to={`/outreach?focus=${r.outreach_id}`}
                    className="text-[12px] text-gold hover:underline"
                  >
                    Open the outreach record
                  </Link>
                )}
                {r.from_email && (
                  <a
                    href={`https://mail.google.com/mail/u/0/#search/${encodeURIComponent(r.from_email)}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[12px] text-latte/50 hover:text-latte hover:underline"
                  >
                    Answer in Gmail
                  </a>
                )}
                {!r.handled && (
                  <button
                    type="button"
                    onClick={() => void ignore(r)}
                    className="text-[12px] text-latte/40 hover:text-latte/70"
                  >
                    Mark dealt with
                  </button>
                )}
              </div>
            </div>
              ))}
            </>
          )}
        </PaginatedList>
      )}
    </Card>
  )
}


/* ------------------------------------------------------ combined companies */

/* --------------------------------------------------------- what was skipped */

const SKIP_HEADING: Record<string, string> = {
  duplicate: 'Already written to',
  skipped: 'Nothing to write to',
  failed: 'Tried, and did not arrive',
}

const SKIP_NOTE: Record<string, string> = {
  duplicate:
    'This mailbox had already had the email — from an earlier campaign, from the same file listing it twice, or from a row logged by hand. It was written to once and not again.',
  skipped:
    'The row had no address the mail server would accept, so nothing was sent. The company is still in the queue with the reason on it.',
  failed: 'The message left and was refused. Worth reading the reason before trying again.',
}

/** Every company not written to, and why — across the whole window.
 *
 * These were listed under each individual day, which answers "what happened
 * on Tuesday" but not "did this company ever get the email". A firm listed
 * twice in one file is skipped the second time, and that is the single most
 * common question about a campaign: it looks like a company was missed when
 * in fact it was written to once, deliberately.
 *
 * The location travels with the name because it is the only thing that tells
 * two firms of the same name apart, and the address because that is what the
 * decision was actually made about.
 */
function NotWrittenTo({ report }: { report: DailyReport }) {
  const rows = report.days.flatMap((d) => d.not_sent.map((x) => ({ ...x, day: d.day })))
  if (rows.length === 0) return null

  const byOutcome = rows.reduce<Record<string, typeof rows>>((acc, r) => {
    ;(acc[r.outcome] ||= []).push(r)
    return acc
  }, {})

  return (
    <Card>
      <div className="mb-3 flex items-center gap-2.5">
        <SkipForward size={17} className="text-gold" />
        <div>
          <h2 className="font-display text-lg text-latte">Not written to, and why</h2>
          <p className="text-[11px] text-latte/45">
            {rows.length} row{rows.length === 1 ? '' : 's'} the agent decided against. Nothing here
            was lost — each was a decision, with a reason.
          </p>
        </div>
      </div>

      <div className="space-y-4">
        {Object.entries(byOutcome).map(([outcome, list]) => (
          <div key={outcome}>
            <p className="text-[12px] font-medium text-latte/70">
              {SKIP_HEADING[outcome] ?? outcome}
              <span className="ml-1.5 text-latte/40">
                · {list.length} row{list.length === 1 ? '' : 's'}
              </span>
            </p>
            <p className="mt-0.5 text-[11px] leading-relaxed text-latte/40">
              {SKIP_NOTE[outcome] ?? ''}
            </p>

            <div className="mt-2 overflow-x-auto">
              <table className="w-full min-w-[34rem] border-collapse text-[11.5px]">
                <thead>
                  <tr className="text-left text-latte/40">
                    <th className="py-1 pr-3 font-normal">Company</th>
                    <th className="py-1 pr-3 font-normal">Where</th>
                    <th className="py-1 pr-3 font-normal">Address</th>
                    <th className="py-1 font-normal">Why</th>
                  </tr>
                </thead>
                <tbody>
                  {list.map((r, i) => (
                    <tr
                      key={`${r.email}-${r.day}-${i}`}
                      className="border-t border-caramel/10 align-top"
                    >
                      <td className="py-1.5 pr-3 text-latte/80">{r.company}</td>
                      <td className="py-1.5 pr-3 text-latte/45">
                        {[r.location, r.country].filter(Boolean).join(', ') || '—'}
                      </td>
                      <td className="py-1.5 pr-3 break-all text-latte/55">{r.email ?? '—'}</td>
                      <td className="py-1.5 text-latte/50">{r.reason ?? r.outcome}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}

function Figure({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <div>
      <p className={`font-body text-2xl font-semibold ${tone ?? 'text-latte'}`}>{value}</p>
      <p className="text-[10.5px] uppercase tracking-wider text-latte/45">{label}</p>
    </div>
  )
}
