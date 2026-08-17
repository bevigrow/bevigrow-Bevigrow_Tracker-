/**
 * Where the prospecting is concentrated, and where it is landing.
 *
 * One chart, deliberately. There was a companies table beside this, and it
 * had to go for two reasons. It did not respond when a country was clicked,
 * so two panels sat side by side disagreeing about what was selected — the
 * left one filtered, the right one carried on showing everything. And the
 * list below is already the companies, in full, searchable: the table was a
 * shorter copy of it wearing a chart's clothes.
 *
 * Countries earn a chart because their volumes genuinely differ, so bar
 * length ranks them at a glance. Clicking one filters the list, which is what
 * makes this a way into the records rather than a second screen to read.
 *
 * It draws on the shared bar chart rather than its own SVG. The hand-rolled
 * version encoded replies as a second bar drawn over the first from the same
 * origin, which reads as two totals rather than a part of one — and it had no
 * table view, so the split was unavailable to anyone reading with a screen
 * reader or unable to separate the two hues. Stacking the same numbers gives
 * the eye a whole to divide, and comes with the table for free.
 */
import { ChartFrame, LegendItem, SplitBarChart, SplitBarTable } from './charts'
import { Skeleton } from './ui'
import type { OutreachInsights as Insights } from '../lib/types'
import { CATEGORICAL } from '../lib/viz'

const REPLIED = CATEGORICAL[2]
const QUIET = CATEGORICAL[0]

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
  if (loading) return <Skeleton className="h-64" />
  if (!data || !data.by_country.length) return null

  const bars = data.by_country.map((r) => ({
    label: r.label,
    primary: r.replied,
    secondary: Math.max(0, r.total - r.replied),
    // A reply rate off two messages is noise, so it only appears once there
    // is enough behind it to mean something.
    meta: [
      r.total >= 5 ? `${r.reply_rate}% reply rate` : null,
      r.follow_ups ? `${r.follow_ups} follow-up${r.follow_ups === 1 ? '' : 's'} sent` : null,
    ]
      .filter(Boolean)
      .join(' · '),
  }))

  const shown = data.by_country.length
  const hidden = Math.max(0, data.countries_tracked - shown)

  return (
    <ChartFrame
      title="Countries"
      subtitle={
        `${data.countries_tracked} tracked · ${data.companies_tracked} companies · ` +
        `tap a country to filter the list` +
        (hidden ? ` · ${hidden} smaller ${hidden === 1 ? 'country' : 'countries'} not charted` : '')
      }
      legend={
        <>
          <LegendItem color={REPLIED} label="Replied" />
          <LegendItem color={QUIET} label="No reply yet" />
        </>
      }
      table={
        <SplitBarTable
          data={bars}
          head="Country"
          primaryLabel="Replied"
          secondaryLabel="No reply"
        />
      }
    >
      <SplitBarChart
        data={bars}
        primaryLabel="Replied"
        secondaryLabel="No reply yet"
        primaryColor={REPLIED}
        secondaryColor={QUIET}
        selected={active || null}
        onSelect={onPick}
        maxRows={10}
        rowNoun="countries"
      />
    </ChartFrame>
  )
}
