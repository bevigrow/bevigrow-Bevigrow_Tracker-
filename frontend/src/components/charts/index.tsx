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

import { compactMoney } from '../../lib/format'
import {
  AXIS_TEXT,
  CATEGORICAL,
  CHART_SURFACE,
  GRID,
  METER_TRACK,
  ROAST_RAMP,
  niceMax,
  roastForValue,
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
    return <p className="py-10 text-center text-sm text-latte/40">No pipeline data yet.</p>
  }

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 620 ${height}`}
        className="w-full"
        style={{ height: Math.max(height, 80) }}
        role="img"
        aria-label="Pipeline volume by stage"
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
          i % 3 === 0 || i === labels.length - 1 ? (
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

export interface MapMarker {
  country: string
  count: number
  value_usd: number
  left: number
  top: number
}

/**
 * Simplified continent outlines in equirectangular space (0–360 × 0–180).
 * Deliberately low-detail — this is a backdrop that gives the markers a sense
 * of place, not a cartographic reference.
 */
const CONTINENTS: string[] = [
  // North America
  'M18 34 L52 28 L84 30 L96 40 L92 52 L104 50 L112 58 L106 70 L92 76 L86 92 L74 96 L66 86 L58 70 L44 62 L30 56 L20 46 Z',
  // Greenland
  'M104 18 L128 14 L138 24 L132 36 L114 38 L102 30 Z',
  // Central America
  'M86 96 L98 94 L106 104 L100 112 L90 106 Z',
  // South America
  'M104 112 L122 108 L134 118 L136 136 L128 156 L116 170 L106 164 L102 146 L98 128 Z',
  // Africa
  'M168 84 L196 78 L214 82 L220 96 L214 112 L204 130 L192 146 L180 142 L172 124 L166 106 Z',
  // Europe
  'M166 42 L192 36 L208 40 L206 52 L192 62 L176 66 L166 58 Z',
  // Middle East / West Asia
  'M210 62 L232 58 L242 68 L238 80 L222 84 L212 76 Z',
  // Asia
  'M208 26 L262 20 L306 26 L322 40 L316 56 L296 66 L272 62 L248 56 L224 52 L210 42 Z',
  // India
  'M244 74 L262 70 L268 82 L258 98 L248 92 Z',
  // South-east Asia
  'M270 82 L290 78 L302 88 L296 100 L280 98 L270 92 Z',
  // Indonesia / Philippines
  'M286 100 L312 96 L320 104 L306 110 L288 108 Z',
  // Australia
  'M300 122 L328 118 L340 130 L334 146 L314 150 L300 138 Z',
  // New Zealand
  'M344 146 L352 144 L354 156 L346 158 Z',
]

/**
 * Buyer/supplier markers on a simplified equirectangular world. Marker area
 * encodes deal count; the sequential roast ramp reinforces it (redundant
 * encoding, so size alone still works in grayscale).
 */
export function WorldMap({ markers }: { markers: MapMarker[] }) {
  const [tip, setTip] = useState<{ m: MapMarker; x: number; y: number } | null>(null)
  const max = Math.max(1, ...markers.map((m) => m.count))

  return (
    <div className="relative">
      <div
        className="relative w-full overflow-hidden rounded-xl border border-caramel/15 bg-bean/40"
        style={{ aspectRatio: '2 / 1' }}
      >
        {/* Landmasses + graticule as a recessive backdrop. The viewBox is a
            plain equirectangular grid (lon -180..180 → 0..360, lat 90..-90 →
            0..180), which is the same projection projectToPercent() uses, so
            markers land on the right continents. */}
        <svg viewBox="0 0 360 180" className="absolute inset-0 h-full w-full" aria-hidden>
          <g fill="rgba(245,230,211,0.09)" stroke="rgba(245,230,211,0.16)" strokeWidth={0.4}>
            {CONTINENTS.map((d, i) => (
              <path key={i} d={d} />
            ))}
          </g>
          {[30, 60, 120, 150].map((y) => (
            <line key={y} x1={0} y1={y} x2={360} y2={y} stroke={GRID} strokeWidth={0.4} />
          ))}
          {[60, 120, 180, 240, 300].map((x) => (
            <line key={x} x1={x} y1={0} x2={x} y2={180} stroke={GRID} strokeWidth={0.4} />
          ))}
          {/* Equator */}
          <line x1={0} y1={90} x2={360} y2={90} stroke="rgba(245,230,211,0.16)" strokeWidth={0.7} />
        </svg>

        {markers.map((m) => {
          const t = m.count / max
          const r = 7 + t * 15
          const color = roastForValue(m.count, max)
          return (
            <button
              key={m.country}
              className="absolute -translate-x-1/2 -translate-y-1/2 rounded-full transition-transform duration-200 hover:scale-125 focus:outline-none focus-visible:ring-2 focus-visible:ring-gold"
              style={{ left: `${m.left}%`, top: `${m.top}%`, width: r, height: r }}
              onMouseEnter={(e) => {
                const host = e.currentTarget.parentElement!.getBoundingClientRect()
                const b = e.currentTarget.getBoundingClientRect()
                setTip({ m, x: b.left - host.left + b.width / 2, y: b.top - host.top })
              }}
              onFocus={(e) => {
                const host = e.currentTarget.parentElement!.getBoundingClientRect()
                const b = e.currentTarget.getBoundingClientRect()
                setTip({ m, x: b.left - host.left + b.width / 2, y: b.top - host.top })
              }}
              onMouseLeave={() => setTip(null)}
              onBlur={() => setTip(null)}
              aria-label={`${m.country}: ${m.count} accounts`}
            >
              <span
                className="absolute inset-0 rounded-full"
                style={{ background: color, boxShadow: `0 0 ${r}px ${color}` }}
              />
              <span
                className="absolute inset-0 rounded-full"
                style={{ border: `2px solid ${CHART_SURFACE}` }}
              />
            </button>
          )
        })}

        {!markers.length && (
          <div className="absolute inset-0 flex items-center justify-center text-sm text-latte/40">
            No international buyers mapped yet.
          </div>
        )}

        {tip && (
          <div
            className="pointer-events-none absolute z-20 -translate-x-1/2 -translate-y-full rounded-lg border border-caramel/35 bg-bean/95 px-3 py-2 text-xs shadow-cup backdrop-blur"
            style={{ left: tip.x, top: tip.y - 6 }}
          >
            <div className="font-semibold capitalize text-latte">{tip.m.country}</div>
            <div className="text-latte/65">{tip.m.count} accounts</div>
            <div className="text-latte/45">{compactMoney(tip.m.value_usd)} pipeline</div>
          </div>
        )}
      </div>

      {/* Ramp legend — size and colour both encode count */}
      <div className="mt-3 flex items-center justify-between text-[11px] text-latte/45">
        <span>Fewer accounts</span>
        <div className="flex items-center gap-1">
          {ROAST_RAMP.map((c) => (
            <span key={c} className="h-2.5 w-7 rounded-sm" style={{ background: c }} />
          ))}
        </div>
        <span>More accounts</span>
      </div>
    </div>
  )
}
