/**
 * Where the prospecting is concentrated, and where it is actually landing.
 *
 * Two panels, two deliberately different forms:
 *
 *   Countries get a bar chart. Volume varies between them, so length carries
 *   real meaning and the eye ranks them instantly.
 *
 *   Companies get a table. In a prospecting log each company is usually a
 *   single row, so a bar chart of company counts is a column of identical
 *   bars — a chart that looks like analysis while saying nothing. The useful
 *   company question is "where does each one stand and who is owed a chase",
 *   which is a table's job. It becomes a ranking as soon as follow-ups
 *   accumulate, because the rows sort by effort spent.
 *
 * Both are clickable: picking a country or a company filters the list below,
 * so the summary is a way into the records rather than a separate read-only
 * screen.
 */
import { useMemo } from 'react'

import { AXIS_TEXT, GRID, niceMax, roastForValue, ticksFor } from '../lib/viz'
import type { OutreachGroup, OutreachInsights as Insights } from '../lib/types'
import { Skeleton } from './ui'

const GOOD = '#4FD18B'

function Panel({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle: string
  children: React.ReactNode
}) {
  return (
    <div className="card p-5">
      <h3 className="font-display text-lg text-latte">{title}</h3>
      <p className="mb-4 mt-0.5 text-xs text-latte/45">{subtitle}</p>
      {children}
    </div>
  )
}

/* ------------------------------------------------------------- countries */

function CountryChart({
  rows,
  active,
  onPick,
}: {
  rows: OutreachGroup[]
  active: string
  onPick: (label: string) => void
}) {
  const max = useMemo(() => niceMax(Math.max(1, ...rows.map((r) => r.total))), [rows])
  const ticks = useMemo(() => ticksFor(max), [max])

  const rowH = 42
  const labelW = 116
  const padR = 44
  const width = 560
  const plotW = width - labelW - padR

  return (
    <>
      <svg
        viewBox={`0 0 ${width} ${rows.length * rowH + 18}`}
        className="w-full"
        style={{ height: rows.length * rowH + 18 }}
        role="img"
        aria-label="Prospects contacted per country, with how many replied"
      >
        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={labelW + (plotW * t) / max}
              y1={0}
              x2={labelW + (plotW * t) / max}
              y2={rows.length * rowH}
              stroke={GRID}
              strokeWidth={1}
            />
            <text
              x={labelW + (plotW * t) / max}
              y={rows.length * rowH + 13}
              fill={AXIS_TEXT}
              fontSize={10}
              textAnchor="middle"
            >
              {t}
            </text>
          </g>
        ))}

        {rows.map((r, i) => {
          const y = i * rowH
          const barW = Math.max(2, (plotW * r.total) / max)
          const repliedW = r.replied ? Math.max(2, (plotW * r.replied) / max) : 0
          const isActive = active === r.label
          return (
            <g
              key={r.label}
              onClick={() => onPick(r.label)}
              style={{ cursor: 'pointer' }}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onPick(r.label)
                }
              }}
              aria-label={`${r.label}: ${r.total} contacted, ${r.replied} replied. Filter the list.`}
            >
              {/* Hit target spans the whole row, not just the bar. */}
              <rect
                x={0}
                y={y}
                width={width}
                height={rowH}
                fill={isActive ? 'rgba(217,160,91,0.10)' : 'transparent'}
                rx={8}
              />
              <text x={0} y={y + 22} fill="rgba(245,230,211,0.85)" fontSize={12}>
                {r.label.length > 16 ? r.label.slice(0, 15) + '…' : r.label}
              </text>

              <rect
                x={labelW}
                y={y + 11}
                width={barW}
                height={18}
                rx={4}
                fill={roastForValue(r.total, max)}
              />
              {/* Replied sits on the same bar with a 2px surface gap, so the
                  part that worked is visible without a second axis. */}
              {repliedW > 0 && (
                <rect
                  x={labelW}
                  y={y + 11}
                  width={repliedW}
                  height={18}
                  rx={4}
                  fill={GOOD}
                  stroke="#33200F"
                  strokeWidth={2}
                />
              )}
              <text
                x={labelW + barW + 8}
                y={y + 24}
                fill="rgba(245,230,211,0.85)"
                fontSize={12}
                fontWeight={600}
              >
                {r.total}
              </text>
            </g>
          )
        })}
      </svg>

      <div className="mt-3 flex flex-wrap items-center gap-4 text-[11px] text-latte/50">
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm" style={{ background: roastForValue(max, max) }} />
          Contacted
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm" style={{ background: GOOD }} />
          Replied
        </span>
      </div>
    </>
  )
}

/* ------------------------------------------------------------- companies */

function CompanyTable({
  rows,
  active,
  onPick,
}: {
  rows: OutreachGroup[]
  active: string
  onPick: (label: string) => void
}) {
  return (
    <div className="-mx-2 overflow-x-auto">
      <table className="w-full min-w-[340px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-caramel/15">
            <th className="table-head">Company</th>
            <th className="table-head text-right">Chases</th>
            <th className="table-head text-right">Replied</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.label}
              onClick={() => onPick(r.label)}
              className={`cursor-pointer border-b border-caramel/10 transition last:border-0 hover:bg-latte/[0.04] ${
                active === r.label ? 'bg-gold/[0.10]' : ''
              }`}
            >
              <td className="px-3 py-2.5 text-latte/85">{r.label}</td>
              <td className="px-3 py-2.5 text-right tabular-nums text-latte/70">
                {r.follow_ups || '—'}
              </td>
              <td className="px-3 py-2.5 text-right">
                {r.replied ? (
                  <span className="font-semibold" style={{ color: GOOD }}>
                    yes
                  </span>
                ) : (
                  <span className="text-latte/35">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ------------------------------------------------------------------ shell */

export function OutreachInsights({
  data,
  loading,
  active,
  onPick,
}: {
  data: Insights | null
  loading: boolean
  active: string
  onPick: (label: string) => void
}) {
  if (loading) {
    return (
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <Skeleton className="h-64" />
        <Skeleton className="h-64" />
      </div>
    )
  }
  if (!data || (!data.by_country.length && !data.by_company.length)) return null

  return (
    <div className="grid items-start gap-4 lg:grid-cols-2">
      {data.by_country.length > 0 && (
        <Panel
          title="Countries"
          subtitle={`${data.countries_tracked} tracked · tap a country to filter the list`}
        >
          <CountryChart rows={data.by_country} active={active} onPick={onPick} />
        </Panel>
      )}
      {data.by_company.length > 0 && (
        <Panel
          title="Companies"
          subtitle={`${data.companies_tracked} tracked · most-chased first · tap to filter`}
        >
          <CompanyTable rows={data.by_company} active={active} onPick={onPick} />
        </Panel>
      )}
    </div>
  )
}
