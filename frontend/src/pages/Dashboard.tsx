import {
  Clock,
  Download,
  Globe2,
  RefreshCw,
  Sparkles,
  TrendingUp,
  X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import {
  BarTable,
  ChartFrame,
  LegendItem,
  RoastBarChart,
  SplitBarChart,
  SplitBarTable,
  TrendChart,
  TrendTable,
} from '../components/charts'
import { Button, Card, EmptyState, Select, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import {
  CHANNEL_META,
  compactMoney,
  formatDateTime,
  relativeDays,
  statusLabel,
} from '../lib/format'
import { useToast } from '../lib/toast'
import type { Dashboard as DashboardData, Insight } from '../lib/types'
import { CATEGORICAL } from '../lib/viz'

/** Periods offered for the activity trend.
 *
 * Named rather than numeric, because "this month" is the question people
 * actually ask and "the last 30 days" is not the same thing on the 3rd. Each
 * resolves to a real date range; a long one is grouped by week or by calendar
 * month so a year does not become 365 unreadable marks.
 */
const PERIODS = [
  { value: '14', label: 'Last 14 days' },
  { value: '30', label: 'Last 30 days' },
  { value: '90', label: 'Last 90 days' },
  { value: 'this-month', label: 'This month' },
  { value: 'last-month', label: 'Last month' },
  { value: 'this-year', label: 'This year' },
  { value: 'custom', label: 'Choose dates…' },
]

const iso = (d: Date) => d.toISOString().slice(0, 10)

/** A named period as an actual pair of dates. */
function resolvePeriod(value: string): { days?: number; date_from?: string; date_to?: string } {
  const now = new Date()
  switch (value) {
    case 'this-month':
      return { date_from: iso(new Date(now.getFullYear(), now.getMonth(), 1)), date_to: iso(now) }
    case 'last-month':
      return {
        date_from: iso(new Date(now.getFullYear(), now.getMonth() - 1, 1)),
        date_to: iso(new Date(now.getFullYear(), now.getMonth(), 0)),
      }
    case 'this-year':
      return { date_from: iso(new Date(now.getFullYear(), 0, 1)), date_to: iso(now) }
    default:
      return { days: Number(value) || 14 }
  }
}

const same = (a: string, b: string) =>
  a.trim().replace(/\s+/g, ' ').toLowerCase() === b.trim().replace(/\s+/g, ' ').toLowerCase()

export function Dashboard() {
  const { user } = useAuth()
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const [data, setData] = useState<DashboardData | null>(null)
  const [insight, setInsight] = useState<Insight | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [refreshingAi, setRefreshingAi] = useState(false)

  // The filters live in the URL, so a filtered dashboard can be reloaded,
  // bookmarked or pasted to a colleague and still say the same thing.
  const country = params.get('country') ?? ''
  const tradeType = params.get('trade_type') ?? ''
  const period = params.get('period') ?? '14'
  const from = params.get('from') ?? ''
  const to = params.get('to') ?? ''
  const query = params.toString()

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  // The AI insight is deliberately NOT awaited alongside the numbers.
  //
  // These two calls used to share a Promise.all, so the whole dashboard waited
  // on whichever was slower — and the insight is a round trip to an LLM,
  // routinely two seconds on its own. The figures a person actually came for
  // sat behind a spinner waiting for a commentary panel.
  //
  // It is also outside the filter effect: the briefing summarises the whole
  // desk, so re-billing a model every time a country is picked would buy
  // nothing. Its failure stays non-fatal.
  useEffect(() => {
    api
      .insights()
      .then(setInsight)
      .catch(() => setInsight(null))
  }, [])

  useEffect(() => {
    let live = true
    setBusy(true)
    const filters = new URLSearchParams(query)
    api
      .dashboard({
        country: filters.get('country') ?? undefined,
        trade_type: filters.get('trade_type') ?? undefined,
        ...(filters.get('period') === 'custom'
          ? { date_from: filters.get('from') ?? undefined, date_to: filters.get('to') ?? undefined }
          : resolvePeriod(filters.get('period') ?? '14')),
      })
      .then((d) => live && setData(d))
      .catch(() => live && toast.error('Could not load the dashboard.'))
      .finally(() => {
        if (!live) return
        setLoading(false)
        setBusy(false)
      })
    return () => {
      live = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query])

  const refreshInsight = async () => {
    setRefreshingAi(true)
    try {
      setInsight(await api.insights(true))
      toast.success('Fresh insights brewed.')
    } catch {
      toast.error('Could not refresh insights.')
    } finally {
      setRefreshingAi(false)
    }
  }

  if (loading) return <Spinner label="Brewing your dashboard…" />
  if (!data) {
    return (
      <EmptyState
        emoji="☕"
        title="The dashboard couldn't be poured"
        hint="Check that the BeviGrow API is reachable, then try again."
        action={<Button onClick={() => location.reload()}>Retry</Button>}
      />
    )
  }

  const k = data.kpis
  const firstName = user?.name?.split(' ')[0] ?? 'there'

  // The row the country filter currently points at. Matched loosely, because
  // the value can arrive from a hand-edited URL in any capitalisation, and the
  // highlight should still land on the right bar.
  const selected = country ? data.by_country.find((c) => same(c.country, country)) : undefined
  const countryOptions = [
    { value: '', label: 'All countries' },
    // A country from a shared link that no longer has records still has to be
    // selectable, or the dropdown would silently disagree with the figures.
    ...(country && !selected ? [{ value: country, label: country }] : []),
    ...data.by_country
      .filter((c) => c.country !== 'Unknown')
      .map((c) => ({ value: c.country, label: `${c.country} · ${c.count + c.prospects}` })),
  ]
  const activeFilters = [country, tradeType].filter(Boolean).length

  /** Carry the country through to the quotes list, so the drill-down agrees. */
  const quotesLink = (trade: string) =>
    `/app/trade/quotes?trade_type=${trade}` +
    (country ? `&country=${encodeURIComponent(selected?.country ?? country)}` : '')

  // Three tiles, not six. "New leads", "Shipments in progress" and
  // "Completed orders" were each the count of a single pipeline stage, and the
  // Pipeline by Stage chart immediately below plots every stage — so they
  // restated a chart the eye had not reached yet. What survives is what that
  // chart cannot say: the export/import split, which is a different dimension
  // entirely, and follow-ups due, which is about time rather than stage.
  const KPI_CARDS = [
    { icon: Globe2, label: 'Export Orders', value: k.export_orders, tint: CATEGORICAL[0], to: quotesLink('export') },
    { icon: Download, label: 'Import Orders', value: k.import_orders, tint: CATEGORICAL[1], to: quotesLink('import') },
    { icon: Clock, label: 'Pending Follow-ups', value: k.pending_follow_ups, tint: '#D9705B', to: '/app/trade/follow-ups' },
  ]

  const pipelineBars = data.by_status
    .filter((s) => s.count > 0)
    .map((s) => ({ label: statusLabel(s.status), value: s.count }))

  const trendSeries = [
    { name: 'Interactions', values: data.trend.map((t) => t.activities), color: CATEGORICAL[0] },
    { name: 'New leads', values: data.trend.map((t) => t.new_leads), color: CATEGORICAL[1] },
  ]

  const countryBars = data.by_country.map((c) => ({
    label: c.country,
    primary: c.count,
    secondary: c.prospects,
    meta: c.value_usd > 0 ? `${compactMoney(c.value_usd)} in deals` : undefined,
    // Records with no country cannot be filtered to — there is nothing to
    // match on — so the row stays visible but inert.
    selectable: c.country !== 'Unknown',
  }))

  return (
    <div className="space-y-6">
      {/* ------------------------------------------------------- greeting */}
      <div className="relative overflow-hidden rounded-2xl border border-caramel/20 bg-roast-gradient p-7">
        <div className="pointer-events-none absolute -right-12 -top-12 h-52 w-52 rounded-full bg-gold/15 blur-3xl" />
        <div className="relative flex flex-wrap items-end justify-between gap-6">
          <div>
            <h1 className="font-display text-3xl text-latte sm:text-4xl">
              {data.greeting} ☕
            </h1>
            <p className="mt-2 text-sm text-latte/55">
              {firstName}, you have{' '}
              <span className="font-semibold text-gold">{k.pending_follow_ups}</span> follow-up
              {k.pending_follow_ups === 1 ? '' : 's'} due and{' '}
              <span className="font-semibold text-gold">{k.activities_today}</span> interaction
              {k.activities_today === 1 ? '' : 's'} logged today
              {activeFilters > 0 && (
                <>
                  {' '}
                  in{' '}
                  <span className="font-semibold text-gold">
                    {[selected?.country ?? country, tradeType].filter(Boolean).join(' · ')}
                  </span>
                </>
              )}
              .
            </p>
          </div>
          {/* Hero figure — exactly one per view */}
          <div className="text-right">
            <p className="text-[11px] uppercase tracking-[0.2em] text-latte/40">Open deal value</p>
            <p className="font-body text-5xl font-semibold text-latte">
              {compactMoney(k.pipeline_value_usd)}
            </p>
          </div>
        </div>
      </div>

      {/* --------------------------------------------------------- filters */}
      {/* One row, above everything it changes. Country and trade type narrow
          every figure on the page — not just the chart they came from — so a
          filtered dashboard reads as one view rather than a filtered chart
          surrounded by unfiltered totals. */}
      <Card className="!p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Select
            value={tradeType}
            onChange={(e) => setFilter('trade_type', e.target.value)}
            aria-label="Filter by trade type"
            options={[
              { value: '', label: 'All trade types' },
              { value: 'export', label: 'Export' },
              { value: 'import', label: 'Import' },
            ]}
          />
          <Select
            value={selected?.country ?? country}
            onChange={(e) => setFilter('country', e.target.value)}
            aria-label="Filter by country"
            options={countryOptions}
          />
          <Select
            value={period}
            onChange={(e) => setFilter('period', e.target.value === '14' ? '' : e.target.value)}
            aria-label="Period"
            options={PERIODS}
          />
        </div>
        {period === 'custom' && (
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:w-2/3">
            <label className="text-[11px] uppercase tracking-wider text-latte/45">
              From
              <input
                type="date"
                value={from}
                max={to || undefined}
                onChange={(e) => setFilter('from', e.target.value)}
                className="input-field mt-1"
              />
            </label>
            <label className="text-[11px] uppercase tracking-wider text-latte/45">
              To
              <input
                type="date"
                value={to}
                min={from || undefined}
                onChange={(e) => setFilter('to', e.target.value)}
                className="input-field mt-1"
              />
            </label>
          </div>
        )}

        {(activeFilters > 0 || busy) && (
          <div className="mt-3 flex flex-wrap items-center gap-4 text-xs">
            {selected && (
              <span className="text-latte/55">
                {selected.country}:{' '}
                <span className="text-latte/80">{selected.count.toLocaleString()}</span> quote
                {selected.count === 1 ? '' : 's'} ·{' '}
                <span className="text-latte/80">{selected.prospects.toLocaleString()}</span> prospect
                {selected.prospects === 1 ? '' : 's'}
              </span>
            )}
            {activeFilters > 0 && (
              <button
                onClick={() => {
                  // The trend window survives: it is how you are reading the
                  // page, not what you are looking at.
                  const next = new URLSearchParams(params)
                  next.delete('country')
                  next.delete('trade_type')
                  setParams(next, { replace: true })
                }}
                className="inline-flex items-center gap-1.5 text-gold hover:underline"
              >
                <X size={12} />
                Clear {activeFilters} filter{activeFilters === 1 ? '' : 's'}
              </button>
            )}
            {busy && <span className="text-latte/40">Updating…</span>}
          </div>
        )}
      </Card>

      {/* ----------------------------------------------------------- kpis */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {KPI_CARDS.map((card, i) => (
          <div key={card.label} className="animate-fade-in-up-sm" style={{ animationDelay: `${i * 50}ms` }}>
            <Link to={card.to}>
              <Card ripple className="h-full">
                {/* One sparkline per card showed the same series six times,
                    so it decorated rather than informed. */}
                <div
                  className="flex h-10 w-10 items-center justify-center rounded-xl"
                  style={{ background: `${card.tint}22`, color: card.tint }}
                >
                  <card.icon size={19} />
                </div>
                <p className="mt-4 font-body text-3xl font-semibold text-latte">{card.value}</p>
                <p className="mt-1 text-[11px] uppercase tracking-wider text-latte/45">
                  {card.label}
                </p>
              </Card>
            </Link>
          </div>
        ))}
      </div>

      {/* ------------------------------------------------------ briefing */}
      {/* Full width now: this shared a three-column row with a conversion
          meter, and removing the meter left a third of the row empty. */}
      <div>
        <Card>
          <div className="mb-4 flex items-start justify-between gap-4">
            <div className="flex items-center gap-2.5">
              <Sparkles size={18} className="text-gold" />
              <div>
                <h3 className="font-display text-lg text-latte">Today's briefing</h3>
                <p className="text-[11px] text-latte/40">
                  {/* "Written by rule-based" is not a sentence. The server
                      answers instantly from rules while the model writes the
                      real one behind the response, so this state is now
                      common enough to word properly. */}
                  {!insight || insight.model === 'rule-based'
                    ? 'Built-in rules · the written version is on its way'
                    : `Written by ${insight.model}`}
                  {insight?.cached && insight.model !== 'rule-based' ? ' · cached' : ''}
                </p>
              </div>
            </div>
            <Button
              variant="ghost"
              onClick={refreshInsight}
              loading={refreshingAi}
              icon={<RefreshCw size={14} />}
              className="shrink-0 px-3 py-1.5 text-xs"
            >
              Refresh
            </Button>
          </div>

          {insight ? (
            <ul className="space-y-2.5">
              {insight.content
                .split('\n')
                .map((l) => l.replace(/^[-•*]\s*/, '').trim())
                .filter(Boolean)
                .map((line, i) => (
                  <li key={i} className="flex gap-3 text-sm leading-relaxed text-latte/75">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-gold" />
                    {line}
                  </li>
                ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-sm text-latte/40">
              Insights are not available right now.
            </p>
          )}

          {insight && !insight.ai_enabled && (
            <p className="mt-4 rounded-lg border border-caramel/20 bg-bean/40 px-3 py-2 text-[11px] text-latte/45">
              Running on built-in rules. Set <code className="text-gold">ANTHROPIC_API_KEY</code> on
              the backend to enable Claude Haiku narratives.
            </p>
          )}
        </Card>

      </div>

      {/* --------------------------------------------------------- charts */}
      {/* items-start: a grid row stretches its cells to the tallest by
          default, so a pipeline with two stages was drawn in a card sized for
          the fourteen-day trend beside it — mostly empty space. */}
      <div className="grid items-start gap-5 lg:grid-cols-2">
        <ChartFrame
          title="Deals by stage"
          subtitle="How far each deal has got"
          table={<BarTable data={pipelineBars} unit="Accounts" />}
        >
          <RoastBarChart data={pipelineBars} unit="accounts" />
        </ChartFrame>

        <ChartFrame
          title="Activity Trend"
          subtitle={
            data.filters.bucket_days === 1
              ? `Interactions and new leads, ${data.filters.days} days`
              : `Interactions and new leads, per ${data.filters.bucket_days === 7 ? 'week' : 'month'}`
          }
          legend={
            <>
              <LegendItem color={CATEGORICAL[0]} label="Interactions" />
              <LegendItem color={CATEGORICAL[1]} label="New leads" />
            </>
          }
          table={<TrendTable labels={data.trend.map((t) => t.label)} series={trendSeries} />}
        >
          <TrendChart labels={data.trend.map((t) => t.label)} series={trendSeries} />
        </ChartFrame>
      </div>

      {/* Quotes AND prospects. Counting quotes alone drew a country you had
          only ever prospected as nothing at all, so a name typed on the
          outreach form looked like it had been dropped on the way in. */}
      <ChartFrame
        title="Accounts by Country"
        subtitle="Quotes and cold prospects — tap a country to filter the page"
        legend={
          <>
            <LegendItem color={CATEGORICAL[0]} label="Quotes" />
            <LegendItem color={CATEGORICAL[1]} label="Prospects" />
          </>
        }
        table={
          <SplitBarTable
            data={countryBars}
            head="Country"
            primaryLabel="Quotes"
            secondaryLabel="Prospects"
          />
        }
      >
        <SplitBarChart
          data={countryBars}
          primaryLabel="Quotes"
          secondaryLabel="Prospects"
          selected={selected?.country ?? (country || null)}
          onSelect={(label) => setFilter('country', same(label, country) ? '' : label)}
          maxRows={10}
          rowNoun="countries"
        />
      </ChartFrame>

      {/* ------------------------------------------ recent + follow-ups */}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-display text-lg text-latte">Recent Interactions</h3>
            <Link to="/app/trade/activity" className="text-xs text-gold hover:underline">
              View all
            </Link>
          </div>
          {data.recent_activities.length ? (
            <ol className="relative space-y-4 border-l border-caramel/20 pl-5">
              {data.recent_activities.map((a) => (
                <li key={a.id} className="relative">
                  <span className="absolute -left-[26px] top-1.5 flex h-3 w-3 items-center justify-center rounded-full border-2 border-espresso bg-gold" />
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-latte">{a.contact_company}</span>
                    <span className="text-[11px] text-latte/40">
                      {CHANNEL_META[a.channel].icon} {CHANNEL_META[a.channel].label}
                    </span>
                    <span className="text-[11px] text-latte/30">
                      · {formatDateTime(a.occurred_at)}
                    </span>
                  </div>
                  <p className="mt-1 line-clamp-2 text-sm text-latte/60">
                    {a.ai_summary || a.discussion}
                  </p>
                </li>
              ))}
            </ol>
          ) : (
            <EmptyState
              emoji="☕"
              title="No fresh coffee leads brewed today"
              hint="Log your first interaction to start the timeline."
            />
          )}
        </Card>

        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-display text-lg text-latte">Upcoming Follow-ups</h3>
            <Link to="/app/trade/follow-ups" className="text-xs text-gold hover:underline">
              Manage
            </Link>
          </div>
          {data.upcoming_follow_ups.length ? (
            <ul className="space-y-2.5">
              {data.upcoming_follow_ups.map((r) => {
                const overdue = new Date(r.due_date) < new Date(new Date().toDateString())
                return (
                  <li
                    key={r.id}
                    className="flex items-start gap-3 rounded-xl border border-caramel/12 bg-bean/30 px-3.5 py-3"
                  >
                    <TrendingUp
                      size={15}
                      className={overdue ? 'mt-0.5 text-red-300' : 'mt-0.5 text-gold'}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-latte/85">{r.message}</p>
                      <p className="mt-0.5 text-[11px] text-latte/40">
                        {r.contact_company} ·{' '}
                        <span className={overdue ? 'text-red-300' : ''}>
                          {relativeDays(r.due_date)}
                        </span>
                      </p>
                    </div>
                  </li>
                )
              })}
            </ul>
          ) : (
            <EmptyState emoji="🫖" title="Your follow-up cup is empty" hint="Nothing is due." />
          )}
        </Card>
      </div>

    </div>
  )
}
