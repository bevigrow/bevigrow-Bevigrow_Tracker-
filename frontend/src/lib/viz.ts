/**
 * Chart palette for BeviGrow's dark coffee surface.
 *
 * Every value below was produced by the data-viz validator against the dark
 * chart surface (#33200F) — not chosen by eye:
 *
 *   CATEGORICAL (2–3 series)  lightness band PASS · chroma floor PASS
 *                             CVD separation worst ΔE 16.5 (deutan) PASS
 *                             normal-vision floor ΔE 17.2 PASS · contrast ≥3:1 PASS
 *   ROAST (5-step ordinal)    monotone L PASS · adjacent ΔL ≥0.06 PASS
 *                             dark-end contrast 2.50:1 PASS · hue spread 14° PASS
 *
 * Do not substitute "nicer" hues without re-running the validator — the brand
 * colours (#D9A05B, #C68B59) are too light for the dark-mode band and fail.
 */

/** The surface charts are drawn on. The validator was run against this value. */
export const CHART_SURFACE = '#33200F'

/** Fixed categorical order. Never cycled — a 4th series folds into "Other". */
export const CATEGORICAL = ['#B8862F', '#3B9FD8', '#4FA96B'] as const

/** Ordinal roast ramp: deep roast → bright crema, monotonically lighter. */
export const ROAST_RAMP = ['#82582F', '#A0733A', '#BE8E45', '#DCAB63', '#F0CE9B'] as const

/** Track colour for meters — a lighter step of the mark's own ramp at low alpha. */
export const METER_TRACK = 'rgba(240, 206, 155, 0.14)'

/** Recessive grid, one step off the surface. */
export const GRID = 'rgba(245, 230, 211, 0.10)'
export const AXIS_TEXT = 'rgba(245, 230, 211, 0.45)'

/** Map an ordinal position (0..n-1) onto the roast ramp. */
export function roastStep(index: number, total: number): string {
  if (total <= 1) return ROAST_RAMP[ROAST_RAMP.length - 1]
  const t = index / (total - 1)
  const slot = Math.round(t * (ROAST_RAMP.length - 1))
  return ROAST_RAMP[Math.min(ROAST_RAMP.length - 1, Math.max(0, slot))]
}

/** Map a 0..1 magnitude onto the roast ramp (sequential encoding). */
export function roastForValue(value: number, max: number): string {
  if (max <= 0) return ROAST_RAMP[0]
  const t = Math.min(1, Math.max(0, value / max))
  return ROAST_RAMP[Math.min(ROAST_RAMP.length - 1, Math.round(t * (ROAST_RAMP.length - 1)))]
}

/** Round an axis maximum up to a clean tick value. */
export function niceMax(value: number): number {
  if (value <= 0) return 1
  const exp = Math.floor(Math.log10(value))
  const base = Math.pow(10, exp)
  const n = value / base
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10
  return step * base
}

export function ticksFor(max: number, count = 4): number[] {
  const step = max / count
  return Array.from({ length: count + 1 }, (_, i) => Math.round(step * i))
}
