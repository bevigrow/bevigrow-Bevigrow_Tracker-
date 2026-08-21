/**
 * Hand-built SVG charts for the BeviGrow dashboard.
 *
 * Conventions applied throughout (see lib/viz.ts for the validated palette):
 *  - bars ≤24px thick, 4px rounded data-end, square at the baseline
 *  - 2px surface-coloured gap between touching marks
 *  - 2px lines, ≥8px markers with a 2px surface ring
 *  - hairline solid gridlines, recessive
 *  - legend whenever there are ≥2 series; direct labels used sparingly
 *  - all label/value text uses text tokens, never the series colour
 *  - every chart offers a table view for screen readers and CVD users
 */
import { useId, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import {
  AXIS_TEXT,
  CATEGORICAL,
  CHART_SURFACE,
  GRID,
  METER_TRACK,
  ROAST_RAMP,
  niceMax,
  roastForValue,
  roastStep,
  ticksFor,
} from '../../lib/viz'

/* ------------------------------------------------------------ chart frame */

export function ChartFrame({
  title,
  subtitle,
  legend,
  table,
  children,
  action,
}: {
  title: string
  subtitle?: string
  legend?: ReactNode
  table?: ReactNode
  children: ReactNode
  action?: ReactNode
}) {
  const [showTable, setShowTable] = useState(false)
  return (
    <div className="card p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-display text-lg text-latte">{title}</h3>
          {subtitle && <p className="mt-0.5 text-xs text-latte/45">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-2">
          {action}
          {table && (
            <button
              onClick={() => setShowTable((v) => !v)}
              className="rounded-lg border border-caramel/25 px-2.5 py-1 text-[11px] font-medium text-latte/60 transition hover:border-gold/45 hover:text-latte"
              aria-pressed={showTable}
            >
              {showTable ? 'Chart' : 'Table'}
            </button>
          )}
        </div>
      </div>
      {legend && <div className="mb-3 flex flex-wrap items-center gap-4">{legend}</div>}
      {showTable && table ? table : children}
    </div>
  )
}

export function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-xs text-latte/65">
      <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} aria-hidden />
      {label}
    </span>
  )
}

/* ------------------------------------------------------------ tooltip bits */

interface TipState {
  x: number
  y: number
  content: ReactNode
}

function Tooltip({ tip }: { tip: TipState | null }) {
  if (!tip) return null
  return (
    <div
      className="pointer-events-none absolute z-20 -translate-x-1/2 -translate-y-full rounded-lg border border-caramel/35 bg-bean/95 px-3 py-2 text-xs shadow-cup backdrop-blur"
      style={{ left: tip.x, top: tip.y - 10 }}
      role="tooltip"
    >
      {tip.content}
    </div>
  )
}

/* --------------------------------------------------- roast bar chart (H) */

export interface BarDatum {
  label: string
  value: number
  /** Optional override; defaults to the sequential roast ramp by magnitude. */
  color?: string
  meta?: string
}

/**
 * Horizontal bars for pipeline stages. One measure → one sequential ramp, so
 * no legend; the value rides the bar tip as a direct label.
 */
export function RoastBarChart({ data, unit = '' }: { data: BarDatum[]; unit?: string }) {
  const [tip, setTip] = useState<TipState | null>(null)
  const max = Math.max(1, ...data.map((d) => d.value))
  const rowH = 34
  const barH = 18 // ≤24px cap
  const labelW = 148
  const height = data.length * rowH

  if (!data.length) {
    return <p className="py-10 text-center text-sm text-latte/40">Nothing to show yet.</p>
  }

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 620 ${height}`}
        className="w-full"
        style={{ height: Math.max(height, 80) }}
        role="img"
        aria-label="Number of deals at each stage"
      >
        {/* Recessive gridlines */}
        {[0.25, 0.5, 0.75, 1].map((f) => (
          <line
            key={f}
            x1={labelW + (620 - labelW - 60) * f}
            y1={0}
            x2={labelW + (620 - labelW - 60) * f}
            y2={height}
            stroke={GRID}
            strokeWidth={1}
          />
        ))}

        {data.map((d, i) => {
          const w = ((620 - labelW - 60) * d.value) / max
          const y = i * rowH + (rowH - barH) / 2
          const fill = d.color ?? roastForValue(d.value, max)
          return (
            <g
              key={d.label}
              onMouseMove={(e) => {
                const rect = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect()
                setTip({
                  x: e.clientX - rect.left,
                  y: e.clientY - rect.top,
                  content: (
                    <>
                      <div className="font-semibold text-latte">{d.label}</div>
                      <div className="text-latte/65">
                        {d.value.toLocaleString()} {unit}
                      </div>
                      {d.meta && <div className="text-latte/45">{d.meta}</div>}
                    </>
                  ),
                })
              }}
              onMouseLeave={() => setTip(null)}
            >
              {/* Generous hit area, larger than the mark */}
              <rect x={0} y={i * rowH} width={620} height={rowH} fill="transparent" />
              <text
                x={labelW - 12}
                y={i * rowH + rowH / 2 + 4}
                textAnchor="end"
                fontSize={11.5}
                fill={AXIS_TEXT}
              >
                {d.label}
              </text>
              {/* Square at the baseline, 4px rounded at the data end */}
              <path
                d={
                  w < 5
                    ? `M${labelW} ${y} h${Math.max(w, 2)} v${barH} h-${Math.max(w, 2)} Z`
                    : `M${labelW} ${y} h${w - 4} a4 4 0 0 1 4 4 v${barH - 8} a4 4 0 0 1 -4 4 h-${w - 4} Z`
                }
                fill={fill}
              />
              {d.value > 0 && (
                <text
                  x={labelW + w + 10}
                  y={i * rowH + rowH / 2 + 4}
                  fontSize={12}
                  fontWeight={600}
                  fill="rgba(245,230,211,0.85)"
                >
                  {d.value.toLocaleString()}
                </text>
              )}
            </g>
          )
        })}
      </svg>
      <Tooltip tip={tip} />
    </div>
  )
}

export function BarTable({ data, unit = 'Count' }: { data: BarDatum[]; unit?: string }) {
  return (
    <div className="max-h-72 overflow-y-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-espresso">
          <tr>
            <th className="table-head">Stage</th>
            <th className="table-head text-right">{unit}</th>
          </tr>
        </thead>
        <tbody>
          {data.map((d) => (
            <tr key={d.label} className="border-t border-caramel/10">
              <td className="table-cell">{d.label}</td>
              <td className="table-cell text-right tabular-nums">{d.value.toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* -------------------------------------------------- split bar chart (H) */

/** The same shape stood upright: square at the baseline, rounded at the top. */
function capTop(x: number, y: number, w: number, h: number): string {
  const height = Math.max(h, 2)
  if (height < 5) return `M${x} ${y} h${w} v${height} h-${w} Z`
  return `M${x} ${y + 4} a4 4 0 0 1 4 -4 h${w - 8} a4 4 0 0 1 4 4 v${height - 4} h-${w} Z`
}


/** Square at the baseline, 4px rounded at the data end — the house bar shape. */
function capRight(x: number, y: number, w: number, h: number): string {
  const width = Math.max(w, 2)
  if (width < 5) return `M${x} ${y} h${width} v${h} h-${width} Z`
  return `M${x} ${y} h${width - 4} a4 4 0 0 1 4 4 v${h - 8} a4 4 0 0 1 -4 4 h-${width - 4} Z`
}

export interface SplitDatum {
  label: string
  /** Left segment — the primary measure. */
  primary: number
  /** Right segment — a second measure of the same unit, stacked, never summed. */
  secondary: number
  meta?: string
  /** False for rows that exist but cannot be filtered on, e.g. "Unknown". */
  selectable?: boolean
}

/**
 * Two measures of the same unit per row, stacked.
 *
 * Used for countries, where quotes and cold prospects are both "records here"
 * but mean different things: a country with nine prospects and no quotes is
 * worth seeing, and a chart of quotes alone drew it as nothing at all. Stacked
 * rather than side-by-side because the total — how much of the desk sits in
 * that country — is the first thing you read, and the split is the second.
 */
export function SplitBarChart({
  data,
  primaryLabel,
  secondaryLabel,
  primaryColor = CATEGORICAL[0],
  secondaryColor = CATEGORICAL[1],
  selected,
  onSelect,
  maxRows,
  rowNoun = 'rows',
}: {
  data: SplitDatum[]
  primaryLabel: string
  secondaryLabel: string
  /** Both default to the categorical pair; pass a validated colour or neither. */
  primaryColor?: string
  secondaryColor?: string
  selected?: string | null
  onSelect?: (label: string) => void
  /** Draw only the biggest N, with the rest behind a toggle. */
  maxRows?: number
  rowNoun?: string
}) {
  const [tip, setTip] = useState<TipState | null>(null)
  const [expanded, setExpanded] = useState(false)

  // A ranked bar chart has no natural end: countries only accumulate, and a
  // chart tall enough to need scrolling has stopped ranking anything. The
  // long tail stays one click — or one Table press — away rather than gone.
  // The selected row is always drawn, however far down it sits, so filtering
  // by a small country never hides the bar that says so.
  const rows = useMemo(() => {
    if (!maxRows || expanded || data.length <= maxRows) return data
    const head = data.slice(0, maxRows)
    const chosen = selected ? data.find((d) => d.label === selected) : undefined
    return chosen && !head.includes(chosen) ? [...head, chosen] : head
  }, [data, maxRows, expanded, selected])

  const totals = data.map((d) => d.primary + d.secondary)
  const max = Math.max(1, ...totals)
  const rowH = 34
  const barH = 18
  const labelW = 148
  const trackW = 620 - labelW - 60
  const height = rows.length * rowH

  if (!data.length) {
    return <p className="py-10 text-center text-sm text-latte/40">Nothing to show yet.</p>
  }

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 620 ${height}`}
        className="w-full"
        style={{ height: Math.max(height, 80) }}
        role="img"
        aria-label={`${primaryLabel} and ${secondaryLabel} across ${data.length} ${rowNoun}`}
      >
        {[0.25, 0.5, 0.75, 1].map((f) => (
          <line
            key={f}
            x1={labelW + trackW * f}
            y1={0}
            x2={labelW + trackW * f}
            y2={height}
            stroke={GRID}
            strokeWidth={1}
          />
        ))}

        {rows.map((d, i) => {
          const total = d.primary + d.secondary
          const y = i * rowH + (rowH - barH) / 2
          const full = (trackW * total) / max
          // 2px of surface between the two touching marks, taken out of the
          // first segment so the total still reads to scale.
          const gap = d.primary > 0 && d.secondary > 0 ? 2 : 0
          const firstW = total > 0 ? Math.max(0, (full * d.primary) / total - gap) : 0
          const secondW = total > 0 ? (full * d.secondary) / total : 0
          const dim = selected != null && selected !== d.label
          const chosen = selected === d.label
          const pick = onSelect && d.selectable !== false ? () => onSelect(d.label) : undefined

          return (
            <g
              key={d.label}
              opacity={dim ? 0.4 : 1}
              style={pick ? { cursor: 'pointer' } : undefined}
              role={pick ? 'button' : undefined}
              tabIndex={pick ? 0 : undefined}
              aria-pressed={pick ? chosen : undefined}
              onClick={pick}
              onKeyDown={(e) => {
                if (pick && (e.key === 'Enter' || e.key === ' ')) {
                  e.preventDefault()
                  pick()
                }
              }}
              onMouseMove={(e) => {
                const rect = (
                  e.currentTarget.ownerSVGElement as SVGSVGElement
                ).getBoundingClientRect()
                setTip({
                  x: e.clientX - rect.left,
                  y: e.clientY - rect.top,
                  content: (
                    <>
                      <div className="font-semibold text-latte">{d.label}</div>
                      <div className="text-latte/65">
                        {d.primary.toLocaleString()} {primaryLabel.toLowerCase()}
                      </div>
                      <div className="text-latte/65">
                        {d.secondary.toLocaleString()} {secondaryLabel.toLowerCase()}
                      </div>
                      {d.meta && <div className="text-latte/45">{d.meta}</div>}
                      {pick && (
                        <div className="mt-1 text-[10px] text-gold/80">
                          {chosen ? 'Click to clear the filter' : 'Click to filter'}
                        </div>
                      )}
                    </>
                  ),
                })
              }}
              onMouseLeave={() => setTip(null)}
            >
              <rect x={0} y={i * rowH} width={620} height={rowH} fill="transparent" />
              <text
                x={labelW - 12}
                y={i * rowH + rowH / 2 + 4}
                textAnchor="end"
                fontSize={11.5}
                fontWeight={chosen ? 700 : 400}
                fill={chosen ? 'rgba(245,230,211,0.95)' : AXIS_TEXT}
              >
                {d.label}
              </text>

              {/* Square at the baseline; only the segment that ends the bar
                  gets the 4px data-end radius. */}
              {d.primary > 0 &&
                (d.secondary > 0 ? (
                  <rect
                    x={labelW}
                    y={y}
                    width={Math.max(firstW, 2)}
                    height={barH}
                    fill={primaryColor}
                  />
                ) : (
                  <path d={capRight(labelW, y, firstW, barH)} fill={primaryColor} />
                ))}
              {d.secondary > 0 && (
                <path
                  d={capRight(labelW + firstW + gap, y, secondW, barH)}
                  fill={secondaryColor}
                />
              )}

              {total > 0 && (
                <text
                  x={labelW + full + 10}
                  y={i * rowH + rowH / 2 + 4}
                  fontSize={12}
                  fontWeight={600}
                  fill="rgba(245,230,211,0.85)"
                >
                  {total.toLocaleString()}
                </text>
              )}
            </g>
          )
        })}
      </svg>

      {maxRows != null && data.length > maxRows && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="mt-2 text-[11px] text-gold hover:underline"
          aria-expanded={expanded}
        >
          {expanded
            ? `Show the top ${maxRows}`
            : `Show all ${data.length} ${rowNoun} (${data.length - maxRows} more)`}
        </button>
      )}

      <Tooltip tip={tip} />
    </div>
  )
}

export function SplitBarTable({
  data,
  head,
  primaryLabel,
  secondaryLabel,
}: {
  data: SplitDatum[]
  head: string
  primaryLabel: string
  secondaryLabel: string
}) {
  return (
    <div className="max-h-72 overflow-y-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-espresso">
          <tr>
            <th className="table-head">{head}</th>
            <th className="table-head text-right">{primaryLabel}</th>
            <th className="table-head text-right">{secondaryLabel}</th>
          </tr>
        </thead>
        <tbody>
          {data.map((d) => (
            <tr key={d.label} className="border-t border-caramel/10">
              <td className="table-cell">{d.label}</td>
              <td className="table-cell text-right tabular-nums">
                {d.primary.toLocaleString()}
              </td>
              <td className="table-cell text-right tabular-nums">
                {d.secondary.toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ------------------------------------------------------------ line chart */

export interface Series {
  name: string
  values: number[]
  color: string
}

/**
 * Two-series trend with a shared y-axis (never a second axis), crosshair
 * tooltip, and an end marker with a 2px surface ring.
 */
export function TrendChart({ labels, series }: { labels: string[]; series: Series[] }) {
  const gid = useId().replace(/:/g, '')
  const [hover, setHover] = useState<number | null>(null)
  const W = 620
  const H = 220
  const pad = { l: 40, r: 18, t: 14, b: 26 }

  const rawMax = Math.max(1, ...series.flatMap((s) => s.values))
  const max = niceMax(rawMax)
  const ticks = ticksFor(max)
  // Roughly eight dates across, whatever the window length. A fixed
  // every-third-day stride was fine for a fortnight and prints ninety labels
  // on top of each other at ninety days. The last date always shows, and any
  // strided label that would crowd it is dropped instead.
  const labelStride = Math.max(1, Math.ceil(labels.length / 8))

  const px = (i: number) =>
    pad.l + (i * (W - pad.l - pad.r)) / Math.max(1, labels.length - 1)
  const py = (v: number) => H - pad.b - ((H - pad.t - pad.b) * v) / max

  const linePath = (vals: number[]) =>
    vals.map((v, i) => `${i === 0 ? 'M' : 'L'}${px(i)} ${py(v)}`).join(' ')

  const areaPath = (vals: number[]) =>
    `${linePath(vals)} L${px(vals.length - 1)} ${H - pad.b} L${px(0)} ${H - pad.b} Z`

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        style={{ height: H }}
        role="img"
        aria-label="Activity and new-lead trend over the last 14 days"
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect()
          const rel = ((e.clientX - rect.left) / rect.width) * W
          const idx = Math.round(
            ((rel - pad.l) / (W - pad.l - pad.r)) * Math.max(1, labels.length - 1),
          )
          setHover(Math.min(labels.length - 1, Math.max(0, idx)))
        }}
      >
        <defs>
          {series.map((s, i) => (
            <linearGradient key={s.name} id={`${gid}-g${i}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={s.color} stopOpacity={0.18} />
              <stop offset="100%" stopColor={s.color} stopOpacity={0} />
            </linearGradient>
          ))}
        </defs>

        {ticks.map((t, ti) => (
          <g key={`tick-${ti}`}>
            <line x1={pad.l} y1={py(t)} x2={W - pad.r} y2={py(t)} stroke={GRID} strokeWidth={1} />
            <text
              x={pad.l - 8}
              y={py(t) + 4}
              textAnchor="end"
              fontSize={10}
              fill={AXIS_TEXT}
              className="tabular-nums"
            >
              {t.toLocaleString()}
            </text>
          </g>
        ))}

        {labels.map((l, i) =>
          i === labels.length - 1 ||
          (i % labelStride === 0 && labels.length - 1 - i >= labelStride / 2) ? (
            <text key={`lab-${i}`} x={px(i)} y={H - 8} textAnchor="middle" fontSize={10} fill={AXIS_TEXT}>
              {l}
            </text>
          ) : null,
        )}

        {series.map((s, i) => (
          <g key={s.name}>
            <path d={areaPath(s.values)} fill={`url(#${gid}-g${i})`} />
            <path
              d={linePath(s.values)}
              fill="none"
              stroke={s.color}
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            {/* End marker: r≥4 with a 2px surface ring */}
            <circle
              cx={px(s.values.length - 1)}
              cy={py(s.values[s.values.length - 1] ?? 0)}
              r={4.5}
              fill={s.color}
              stroke={CHART_SURFACE}
              strokeWidth={2}
            />
          </g>
        ))}

        {hover !== null && (
          <g>
            <line
              x1={px(hover)}
              y1={pad.t}
              x2={px(hover)}
              y2={H - pad.b}
              stroke="rgba(245,230,211,0.28)"
              strokeWidth={1}
            />
            {series.map((s) => (
              <circle
                key={s.name}
                cx={px(hover)}
                cy={py(s.values[hover] ?? 0)}
                r={4.5}
                fill={s.color}
                stroke={CHART_SURFACE}
                strokeWidth={2}
              />
            ))}
          </g>
        )}
      </svg>

      {hover !== null && (
        <div
          className="pointer-events-none absolute z-20 -translate-x-1/2 rounded-lg border border-caramel/35 bg-bean/95 px-3 py-2 text-xs shadow-cup backdrop-blur"
          style={{ left: `${(px(hover) / W) * 100}%`, top: 6 }}
        >
          <div className="mb-1 font-semibold text-latte">{labels[hover]}</div>
          {series.map((s) => (
            <div key={s.name} className="flex items-center gap-2 text-latte/70">
              <span className="h-2 w-2 rounded-full" style={{ background: s.color }} />
              {s.name}: <span className="tabular-nums text-latte">{s.values[hover] ?? 0}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function TrendTable({ labels, series }: { labels: string[]; series: Series[] }) {
  return (
    <div className="max-h-72 overflow-y-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-espresso">
          <tr>
            <th className="table-head">Day</th>
            {series.map((s) => (
              <th key={s.name} className="table-head text-right">
                {s.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {labels.map((l, i) => (
            <tr key={l + i} className="border-t border-caramel/10">
              <td className="table-cell">{l}</td>
              {series.map((s) => (
                <td key={s.name} className="table-cell text-right tabular-nums">
                  {s.values[i] ?? 0}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ------------------------------------------------------- coffee cup meter */

/**
 * A progress meter shaped like a coffee cup: the fill is the value, the
 * unfilled track is a lighter step of the same ramp so state reads across the
 * whole shape.
 */
export function CupMeter({
  value,
  max = 100,
  label,
  caption,
  color = ROAST_RAMP[4],
  size = 132,
}: {
  value: number
  max?: number
  label: string
  caption?: string
  color?: string
  size?: number
}) {
  const gid = useId().replace(/:/g, '')
  const pct = Math.min(1, Math.max(0, max > 0 ? value / max : 0))
  // Cup interior spans y 26 → 84 in the 120-unit viewBox.
  const top = 26
  const bottom = 84
  const fillTop = bottom - (bottom - top) * pct

  return (
    <div className="flex flex-col items-center gap-2">
      <svg viewBox="0 0 120 120" width={size} height={size} role="img" aria-label={`${label}: ${Math.round(pct * 100)}%`}>
        <defs>
          <clipPath id={`${gid}-cup`}>
            <path d="M30 24 L86 24 L79 84 a10 10 0 0 1 -10 9 L47 93 a10 10 0 0 1 -10 -9 Z" />
          </clipPath>
        </defs>

        {/* Track: lighter step of the same ramp */}
        <path
          d="M30 24 L86 24 L79 84 a10 10 0 0 1 -10 9 L47 93 a10 10 0 0 1 -10 -9 Z"
          fill={METER_TRACK}
        />
        {/* Fill */}
        <g clipPath={`url(#${gid}-cup)`}>
          <rect x={24} y={fillTop} width={72} height={bottom + 14 - fillTop} fill={color} />
          {/* Crema line on the surface of the liquid */}
          {pct > 0.04 && (
            <rect x={24} y={fillTop} width={72} height={3} fill="rgba(251,245,236,0.55)" />
          )}
        </g>

        {/* Cup outline + handle + saucer */}
        <path
          d="M30 24 L86 24 L79 84 a10 10 0 0 1 -10 9 L47 93 a10 10 0 0 1 -10 -9 Z"
          fill="none"
          stroke="rgba(245,230,211,0.5)"
          strokeWidth={2.5}
        />
        <path
          d="M86 34 c 16 0, 16 26, 0 26"
          fill="none"
          stroke="rgba(245,230,211,0.4)"
          strokeWidth={3.5}
          strokeLinecap="round"
        />
        <ellipse cx={58} cy={99} rx={36} ry={5.5} fill="rgba(245,230,211,0.12)" />

        <text
          x={58}
          y={58}
          textAnchor="middle"
          fontSize={19}
          fontWeight={700}
          fill="rgba(251,245,236,0.95)"
          className="tabular-nums"
          style={{ paintOrder: 'stroke', stroke: 'rgba(27,16,10,0.7)', strokeWidth: 3 }}
        >
          {Math.round(pct * 100)}%
        </text>
      </svg>
      <div className="text-center">
        <p className="text-xs font-semibold uppercase tracking-wider text-latte/70">{label}</p>
        {caption && <p className="mt-0.5 text-[11px] text-latte/40">{caption}</p>}
      </div>
    </div>
  )
}

/* --------------------------------------------------------------- sparkline */

export function Sparkline({
  values,
  color = CATEGORICAL[0],
  width = 92,
  height = 28,
}: {
  values: number[]
  color?: string
  width?: number
  height?: number
}) {
  const path = useMemo(() => {
    if (values.length < 2) return ''
    const max = Math.max(1, ...values)
    const min = Math.min(...values)
    const span = max - min || 1
    return values
      .map((v, i) => {
        const x = (i / (values.length - 1)) * width
        const y = height - 3 - ((v - min) / span) * (height - 6)
        return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`
      })
      .join(' ')
  }, [values, width, height])

  if (!path) return null
  return (
    <svg width={width} height={height} aria-hidden className="overflow-visible">
      <path
        d={path}
        fill="none"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={0.75}
      />
    </svg>
  )
}

/* --------------------------------------------------------------- world map */

/* ------------------------------------------------------------------ funnel */

export interface FunnelStep {
  label: string
  value: number
}

/**
 * One population narrowing through stages.
 *
 * A funnel is a ranked bar chart with one extra job: the *drop* between two
 * stages carries as much meaning as the stages themselves, so it is written in
 * the gap rather than left to be worked out. Each step is a subset of the one
 * above, which is what makes that subtraction legitimate — two unrelated
 * measures stacked into a funnel shape is the classic version of this chart
 * that lies.
 *
 * One measure, so one hue: the sequential ramp, darkest where the population is
 * largest. No legend — with a single series the title names it.
 */
export function FunnelChart({ steps, unit = '' }: { steps: FunnelStep[]; unit?: string }) {
  const [tip, setTip] = useState<TipState | null>(null)
  const top = Math.max(1, steps[0]?.value ?? 1)
  const rowH = 58
  const barH = 22
  const labelW = 168
  const trackW = 620 - labelW - 78
  const height = steps.length * rowH

  if (!steps.length) {
    return <p className="py-10 text-center text-sm text-latte/40">Nothing to show yet.</p>
  }

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 620 ${height}`}
        className="w-full"
        style={{ height }}
        role="img"
        aria-label={`Funnel from ${steps[0].label} down to ${steps[steps.length - 1].label}`}
      >
        {steps.map((step, i) => {
          const w = Math.max(2, (trackW * step.value) / top)
          const y = i * rowH + 6
          const previous = i > 0 ? steps[i - 1].value : null
          // The share of the step above that got this far — not of the whole
          // funnel. What you want to know is where people are lost, and that
          // is a comparison with the step immediately before.
          const rate =
            previous && previous > 0 ? Math.round((step.value / previous) * 100) : null

          return (
            <g
              key={step.label}
              onMouseMove={(e) => {
                const rect = (
                  e.currentTarget.ownerSVGElement as SVGSVGElement
                ).getBoundingClientRect()
                setTip({
                  x: e.clientX - rect.left,
                  y: e.clientY - rect.top,
                  content: (
                    <>
                      <div className="font-semibold text-latte">{step.label}</div>
                      <div className="text-latte/65">
                        {step.value.toLocaleString()} {unit}
                      </div>
                      {rate !== null && (
                        <div className="text-latte/45">
                          {rate}% of {steps[i - 1].label.toLowerCase()}
                        </div>
                      )}
                    </>
                  ),
                })
              }}
              onMouseLeave={() => setTip(null)}
            >
              <rect x={0} y={i * rowH} width={620} height={rowH} fill="transparent" />
              <text
                x={labelW - 12}
                y={y + barH / 2 + 4}
                textAnchor="end"
                fontSize={11.5}
                fill={AXIS_TEXT}
              >
                {step.label}
              </text>
              <path
                d={capRight(labelW, y, w, barH)}
                fill={roastStep(steps.length - 1 - i, steps.length)}
              />
              <text
                x={labelW + w + 10}
                y={y + barH / 2 + 4}
                fontSize={13}
                fontWeight={600}
                fill="rgba(245,230,211,0.9)"
              >
                {step.value.toLocaleString()}
              </text>

              {/* The drop, written in the gap it describes. */}
              {rate !== null && (
                <text x={labelW} y={i * rowH - 4} fontSize={10.5} fill={AXIS_TEXT}>
                  {rate}% carried on
                </text>
              )}
            </g>
          )
        })}
      </svg>
      <Tooltip tip={tip} />
    </div>
  )
}

export function FunnelTable({ steps }: { steps: FunnelStep[] }) {
  return (
    <div className="max-h-72 overflow-y-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-espresso">
          <tr>
            <th className="table-head">Stage</th>
            <th className="table-head text-right">Count</th>
            <th className="table-head text-right">Of previous</th>
          </tr>
        </thead>
        <tbody>
          {steps.map((s, i) => {
            const previous = i > 0 ? steps[i - 1].value : null
            return (
              <tr key={s.label} className="border-t border-caramel/10">
                <td className="table-cell">{s.label}</td>
                <td className="table-cell text-right tabular-nums">
                  {s.value.toLocaleString()}
                </td>
                <td className="table-cell text-right tabular-nums text-latte/50">
                  {previous && previous > 0
                    ? `${Math.round((s.value / previous) * 100)}%`
                    : '—'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

/* ------------------------------------------------------------ column chart */

export interface Column {
  label: string
  value: number
  meta?: string
}

/**
 * A value per day, with the ceiling drawn on it.
 *
 * Vertical because the category is time and reads left to right, and because
 * the question is "how close to the limit did we get" — comparing a horizontal
 * bar against a limit line is awkward in a way a column against a horizontal
 * rule is not.
 *
 * The rule is not a series. It is a dashed hairline in the axis colour so it
 * reads as furniture, and it is labelled, because an unlabelled line on a
 * chart is a puzzle.
 */
export function ColumnChart({
  data,
  limit,
  limitLabel = 'limit',
  color = CATEGORICAL[0],
  unit = '',
}: {
  data: Column[]
  limit?: number
  limitLabel?: string
  color?: string
  unit?: string
}) {
  const [hover, setHover] = useState<number | null>(null)
  const W = 620
  const H = 220
  const pad = { l: 34, r: 16, t: 16, b: 30 }

  const peak = Math.max(1, ...data.map((d) => d.value), limit ?? 0)
  const max = niceMax(peak)
  const ticks = ticksFor(max)
  const plotW = W - pad.l - pad.r
  const plotH = H - pad.t - pad.b
  const slot = data.length ? plotW / data.length : plotW
  // A 2px gap between touching marks, and never a bar so wide that a run of
  // days stops reading as a series.
  const barW = Math.max(2, Math.min(slot - 2, 26))
  const y = (v: number) => pad.t + plotH - (plotH * v) / max

  if (!data.length) {
    return <p className="py-10 text-center text-sm text-latte/40">Nothing to show yet.</p>
  }

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        style={{ height: H }}
        role="img"
        aria-label={`${unit || 'Value'} per day`}
        onMouseLeave={() => setHover(null)}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.l} y1={y(t)} x2={W - pad.r} y2={y(t)} stroke={GRID} strokeWidth={1} />
            <text
              x={pad.l - 7}
              y={y(t) + 4}
              textAnchor="end"
              fontSize={10}
              fill={AXIS_TEXT}
              className="tabular-nums"
            >
              {t.toLocaleString()}
            </text>
          </g>
        ))}

        {data.map((d, i) => {
          const cx = pad.l + slot * i + slot / 2
          const topY = y(d.value)
          const h = pad.t + plotH - topY
          return (
            <g key={`${d.label}-${i}`} onMouseMove={() => setHover(i)}>
              <rect
                x={cx - slot / 2}
                y={pad.t}
                width={slot}
                height={plotH}
                fill={hover === i ? 'rgba(245,230,211,0.05)' : 'transparent'}
              />
              {d.value > 0 && (
                <path
                  d={capTop(cx - barW / 2, topY, barW, Math.max(h, 3))}
                  fill={color}
                  opacity={hover === null || hover === i ? 1 : 0.55}
                />
              )}
            </g>
          )
        })}

        {limit !== undefined && limit <= max && (
          <g>
            <line
              x1={pad.l}
              y1={y(limit)}
              x2={W - pad.r}
              y2={y(limit)}
              stroke="rgba(217,160,91,0.55)"
              strokeWidth={1}
              strokeDasharray="4 3"
            />
            <text
              x={W - pad.r}
              y={y(limit) - 5}
              textAnchor="end"
              fontSize={10}
              fill="rgba(217,160,91,0.85)"
            >
              {limit} {limitLabel}
            </text>
          </g>
        )}

        {data.map((d, i) =>
          i % Math.max(1, Math.ceil(data.length / 8)) === 0 ? (
            <text
              key={`lab-${i}`}
              x={pad.l + slot * i + slot / 2}
              y={H - 9}
              textAnchor="middle"
              fontSize={10}
              fill={AXIS_TEXT}
            >
              {d.label}
            </text>
          ) : null,
        )}
      </svg>

      {hover !== null && (
        <div
          className="pointer-events-none absolute z-20 -translate-x-1/2 rounded-lg border border-caramel/35 bg-bean/95 px-3 py-2 text-xs shadow-cup backdrop-blur"
          style={{ left: `${((pad.l + slot * hover + slot / 2) / W) * 100}%`, top: 4 }}
        >
          <div className="font-semibold text-latte">{data[hover].label}</div>
          <div className="text-latte/70">
            {data[hover].value.toLocaleString()} {unit}
          </div>
          {data[hover].meta && <div className="text-latte/45">{data[hover].meta}</div>}
        </div>
      )}
    </div>
  )
}

export function ColumnTable({ data, unit = 'Count' }: { data: Column[]; unit?: string }) {
  return (
    <div className="max-h-72 overflow-y-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-espresso">
          <tr>
            <th className="table-head">Day</th>
            <th className="table-head text-right">{unit}</th>
          </tr>
        </thead>
        <tbody>
          {data.map((d, i) => (
            <tr key={`${d.label}-${i}`} className="border-t border-caramel/10">
              <td className="table-cell">{d.label}</td>
              <td className="table-cell text-right tabular-nums">{d.value.toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ----------------------------------------------------------------- heatmap */

export interface HeatRow {
  label: string
  cells: number[]
}

/**
 * Two categories and one magnitude — a grid, not a stack.
 *
 * Country against month is the case this exists for. Stacking it would need a
 * hue per country, and the palette holds three on purpose; eleven would be
 * eleven guesses at which is which. A grid needs only one hue and reads by
 * density, which is the honest encoding when the question is "where and when
 * was the effort", not "what share was Germany".
 *
 * Empty cells are drawn as an empty cell rather than skipped: a month with no
 * sends is information, and a gap that closes up hides it.
 */
export function Heatmap({
  rows,
  columns,
  unit = '',
}: {
  rows: HeatRow[]
  columns: string[]
  unit?: string
}) {
  const [tip, setTip] = useState<TipState | null>(null)

  if (!rows.length || !columns.length) {
    return <p className="py-10 text-center text-sm text-latte/40">Nothing to show yet.</p>
  }

  const labelW = 128
  const cell = Math.min(44, Math.max(18, (620 - labelW - 8) / columns.length))
  const gap = 2
  const rowH = cell
  const height = rows.length * rowH + 22
  const width = labelW + columns.length * cell
  const max = Math.max(1, ...rows.flatMap((r) => r.cells))

  return (
    <div className="relative overflow-x-auto">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{ height, minWidth: Math.min(width, 620) }}
        className="w-full"
        role="img"
        aria-label={`${unit || 'Value'} per ${rows.length} rows across ${columns.length} months`}
      >
        {columns.map((c, x) => (
          <text
            key={c + x}
            x={labelW + x * cell + cell / 2}
            y={12}
            textAnchor="middle"
            fontSize={9.5}
            fill={AXIS_TEXT}
          >
            {c}
          </text>
        ))}

        {rows.map((row, y) => (
          <g key={row.label}>
            <text
              x={labelW - 10}
              y={22 + y * rowH + rowH / 2 + 3}
              textAnchor="end"
              fontSize={11}
              fill={AXIS_TEXT}
            >
              {row.label.length > 16 ? `${row.label.slice(0, 15)}…` : row.label}
            </text>
            {columns.map((_, x) => {
              const value = row.cells[x] ?? 0
              return (
                <rect
                  key={x}
                  x={labelW + x * cell + gap / 2}
                  y={22 + y * rowH + gap / 2}
                  width={cell - gap}
                  height={rowH - gap}
                  rx={3}
                  fill={value > 0 ? roastForValue(value, max) : 'rgba(245,230,211,0.045)'}
                  onMouseMove={(e) => {
                    const rect = (
                      e.currentTarget.ownerSVGElement as SVGSVGElement
                    ).getBoundingClientRect()
                    setTip({
                      x: e.clientX - rect.left,
                      y: e.clientY - rect.top,
                      content: (
                        <>
                          <div className="font-semibold text-latte">{row.label}</div>
                          <div className="text-latte/65">
                            {columns[x]}: {value.toLocaleString()} {unit}
                          </div>
                        </>
                      ),
                    })
                  }}
                  onMouseLeave={() => setTip(null)}
                />
              )
            })}
          </g>
        ))}
      </svg>
      <Tooltip tip={tip} />
    </div>
  )
}

export function HeatmapTable({
  rows,
  columns,
}: {
  rows: HeatRow[]
  columns: string[]
}) {
  return (
    <div className="max-h-72 overflow-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-espresso">
          <tr>
            <th className="table-head">Country</th>
            {columns.map((c) => (
              <th key={c} className="table-head text-right">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label} className="border-t border-caramel/10">
              <td className="table-cell">{r.label}</td>
              {columns.map((_, i) => (
                <td key={i} className="table-cell text-right tabular-nums">
                  {r.cells[i] ?? 0}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
