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
import { useState } from 'react'

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
  // Volume by default: with almost no replies yet, ranking by rate would put
  // a country with one message and one answer above a country with forty.
  // Once the replies are real, that ordering is the interesting one.
  const [rank, setRank] = useState<'volume' | 'rate'>('volume')

  if (loading) return <Skeleton className="h-64" />
  if (!data || !data.by_country.length) return null

  const ENOUGH = 5 // messages before a percentage means anything

  const ordered = [...data.by_country].sort((a, b) => {
    if (rank === 'volume') return b.total - a.total
    // A rate from two messages is not a rate. Countries below the threshold
    // keep their volume order, underneath the ones that can be judged.
    const aReady = a.total >= ENOUGH
    const bReady = b.total >= ENOUGH
    if (aReady !== bReady) return aReady ? -1 : 1
    if (aReady && b.reply_rate !== a.reply_rate) return b.reply_rate - a.reply_rate
    return b.total - a.total
  })

  const replies = data.by_country.reduce((n, r) => n + r.replied, 0)
  const contacted = data.by_country.reduce((n, r) => n + r.total, 0)

  const bars = ordered.map((r) => ({
    label: r.label,
    primary: r.replied,
    secondary: Math.max(0, r.total - r.replied),
    // A reply rate off two messages is noise, so it only appears once there
    // is enough behind it to mean something.
    meta: [
      // Companies first: "40 emails" and "30 companies" answer different
      // questions, and the one asked of this panel is how far the prospecting
      // has reached, not how much of it there was.
      `${r.companies} compan${r.companies === 1 ? 'y' : 'ies'} · ${r.total} email${r.total === 1 ? '' : 's'}`,
      r.total >= ENOUGH
        ? `${r.reply_rate}% reply rate`
        : `${r.total} sent — too few to judge a rate`,
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
        `${data.countries_tracked} countries · ${data.companies_tracked} companies · ` +
        `${replies} of ${contacted} answered` +
        (hidden ? ` · ${hidden} smaller ${hidden === 1 ? 'country' : 'countries'} not charted` : '')
      }
      action={
        <button
          onClick={() => setRank((r) => (r === 'volume' ? 'rate' : 'volume'))}
          title={
            rank === 'volume'
              ? 'Ordered by how many were written to — click to order by who answers'
              : 'Ordered by reply rate — click to order by volume'
          }
          className="rounded-lg border border-caramel/25 px-2.5 py-1 text-[11px] font-medium text-latte/60 transition hover:border-gold/45 hover:text-latte"
        >
          {rank === 'volume' ? 'By volume' : 'By reply rate'}
        </button>
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
