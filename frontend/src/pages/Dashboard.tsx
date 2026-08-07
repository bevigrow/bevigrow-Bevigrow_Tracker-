import {
  CheckCircle2,
  Clock,
  Coffee,
  Download,
  Globe2,
  RefreshCw,
  Ship,
  Sparkles,
  TrendingUp,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  BarTable,
  ChartFrame,
  CupMeter,
  LegendItem,
  RoastBarChart,
  Sparkline,
  TrendChart,
  TrendTable,
} from '../components/charts'
import { Steam } from '../components/coffee/Ambient'
import { Button, Card, EmptyState, Spinner, StatusBadge } from '../components/ui'
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
import { CATEGORICAL, ROAST_RAMP } from '../lib/viz'

export function Dashboard() {
  const { user } = useAuth()
  const toast = useToast()
  const [data, setData] = useState<DashboardData | null>(null)
  const [insight, setInsight] = useState<Insight | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshingAi, setRefreshingAi] = useState(false)

  const load = useCallback(async () => {
    try {
      const [dash, ins] = await Promise.all([
        api.dashboard(),
        api.insights().catch(() => null),
      ])
      setData(dash)
      setInsight(ins)
    } catch {
      toast.error('Could not load the dashboard.')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    void load()
  }, [load])

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

  const KPI_CARDS = [
    { icon: Coffee, label: 'New Coffee Leads', value: k.new_leads, tint: ROAST_RAMP[4], to: '/app/contacts?status=new_lead' },
    { icon: Globe2, label: 'Export Orders', value: k.export_orders, tint: CATEGORICAL[0], to: '/app/contacts?trade_type=export' },
    { icon: Download, label: 'Import Orders', value: k.import_orders, tint: CATEGORICAL[1], to: '/app/contacts?trade_type=import' },
    { icon: Ship, label: 'Shipments in Progress', value: k.shipments_in_progress, tint: ROAST_RAMP[2], to: '/app/pipeline' },
    { icon: CheckCircle2, label: 'Completed Orders', value: k.completed_orders, tint: CATEGORICAL[2], to: '/app/contacts?status=completed' },
    { icon: Clock, label: 'Pending Follow-ups', value: k.pending_follow_ups, tint: '#D9705B', to: '/app/reminders' },
  ]

  const pipelineBars = data.by_status
    .filter((s) => s.count > 0)
    .map((s) => ({ label: statusLabel(s.status), value: s.count }))

  const trendSeries = [
    { name: 'Interactions', values: data.trend.map((t) => t.activities), color: CATEGORICAL[0] },
    { name: 'New leads', values: data.trend.map((t) => t.new_leads), color: CATEGORICAL[1] },
  ]

  return (
    <div className="space-y-6">
      {/* ------------------------------------------------------- greeting */}
      <div className="relative overflow-hidden rounded-2xl border border-caramel/20 bg-roast-gradient p-7">
        <div className="pointer-events-none absolute -right-12 -top-12 h-52 w-52 rounded-full bg-gold/15 blur-3xl" />
        <Steam count={4} className="absolute left-8 top-0 opacity-50" />
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
              {k.activities_today === 1 ? '' : 's'} logged today.
            </p>
          </div>
          {/* Hero figure — exactly one per view */}
          <div className="text-right">
            <p className="text-[11px] uppercase tracking-[0.2em] text-latte/40">Open pipeline</p>
            <p className="font-body text-5xl font-semibold text-latte">
              {compactMoney(k.pipeline_value_usd)}
            </p>
          </div>
        </div>
      </div>

      {/* ----------------------------------------------------------- kpis */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {KPI_CARDS.map((card, i) => (
          <div key={card.label} className="animate-fade-in-up-sm" style={{ animationDelay: `${i * 50}ms` }}>
            <Link to={card.to}>
              <Card ripple className="h-full">
                <div className="flex items-start justify-between">
                  <div
                    className="flex h-10 w-10 items-center justify-center rounded-xl"
                    style={{ background: `${card.tint}22`, color: card.tint }}
                  >
                    <card.icon size={19} />
                  </div>
                  <Sparkline
                    values={data.trend.map((t) => t.activities)}
                    color={card.tint}
                    width={54}
                    height={22}
                  />
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

      {/* -------------------------------------------------- ai + meters */}
      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div className="flex items-center gap-2.5">
              <Sparkles size={18} className="text-gold" />
              <div>
                <h3 className="font-display text-lg text-latte">AI Dashboard Insights</h3>
                <p className="text-[11px] text-latte/40">
                  {insight?.model ? `Generated by ${insight.model}` : 'Claude Haiku'}
                  {insight?.cached ? ' · cached' : ''}
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

        <Card>
          <h3 className="mb-1 font-display text-lg text-latte">Conversion</h3>
          <p className="mb-4 text-[11px] text-latte/40">Completed vs closed deals</p>
          <div className="flex items-center justify-around">
            <CupMeter
              value={k.conversion_rate}
              max={100}
              label="Win rate"
              caption={`${k.completed_orders} completed`}
              size={128}
            />
            <CupMeter
              value={k.export_orders}
              max={Math.max(1, k.export_orders + k.import_orders)}
              label="Export share"
              caption={`${k.import_orders} import`}
              color={ROAST_RAMP[3]}
              size={128}
            />
          </div>
        </Card>
      </div>

      {/* --------------------------------------------------------- charts */}
      <div className="grid gap-5 lg:grid-cols-2">
        <ChartFrame
          title="Pipeline by Stage"
          subtitle="Accounts at each stage of the coffee trade cycle"
          table={<BarTable data={pipelineBars} unit="Accounts" />}
        >
          <RoastBarChart data={pipelineBars} unit="accounts" />
        </ChartFrame>

        <ChartFrame
          title="Activity Trend"
          subtitle="Interactions and new leads, last 14 days"
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

      <ChartFrame
        title="Accounts by Country"
        subtitle="Where your coffee buyers and suppliers are"
        table={
          <BarTable
            data={data.by_country.map((c) => ({ label: c.country, value: c.count }))}
            unit="Accounts"
          />
        }
      >
        <RoastBarChart
          data={data.by_country.map((c) => ({
            label: c.country,
            value: c.count,
            meta: compactMoney(c.value_usd) + ' pipeline',
          }))}
          unit="accounts"
        />
      </ChartFrame>

      {/* ------------------------------------------ recent + follow-ups */}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-display text-lg text-latte">Recent Interactions</h3>
            <Link to="/app/activities" className="text-xs text-gold hover:underline">
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
            <Link to="/app/reminders" className="text-xs text-gold hover:underline">
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

      {/* ---------------------------------------------------- status mix */}
      <Card>
        <h3 className="mb-4 font-display text-lg text-latte">Status Overview</h3>
        <div className="flex flex-wrap gap-2.5">
          {data.by_status.map((s) => (
            <div
              key={s.status}
              className="flex items-center gap-2 rounded-xl border border-caramel/15 bg-bean/30 px-3 py-2"
            >
              <StatusBadge status={s.status} />
              <span className="font-body text-sm font-semibold tabular-nums text-latte">
                {s.count}
              </span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
