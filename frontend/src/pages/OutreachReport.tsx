/**
 * What was sent, on which day, and what was not sent and why.
 *
 * Read from a ledger that no delete touches. A campaign is a working file:
 * once it is finished, or once it was only a test, it gets thrown away — and
 * with the old design the day's history went with it, so the app forgot it had
 * written to those companies this morning. This page is the memory that
 * outlives the campaign.
 */
import { CalendarDays, Copy, Inbox, RotateCcw, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { Button, Card, ConfirmDialog, EmptyState, Skeleton } from '../components/ui'
import { ApiError, api } from '../lib/api'
import { formatDateTime } from '../lib/format'
import { useToast } from '../lib/toast'
import type { Campaign, DailyReport, DuplicateGroup } from '../lib/types'

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

  const load = useCallback(async () => {
    try {
      const [r, d, b] = await Promise.all([
        api.dailyReport(60),
        api.duplicateReport().catch(() => []),
        api.listCampaigns(true).catch(() => []),
      ])
      setReport(r)
      setDupes(d)
      setBinned(b)
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

      {/* ------------------------------------------------ same name report */}
      {dupes.length > 0 && (
        <Card>
          <div className="mb-3 flex items-center gap-2.5">
            <Copy size={17} className="text-gold" />
            <div>
              <h2 className="font-display text-lg text-latte">Same name, different company</h2>
              <p className="text-[11px] text-latte/45">
                Each was written to separately, because the address and mailbox differ. Worth a
                look in case any pair is really one business.
              </p>
            </div>
          </div>
          <div className="space-y-3">
            {dupes.map((g) => (
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
          </div>
        </Card>
      )}

      {/* ----------------------------------------------------------- days */}
      {!report?.days.length ? (
        <EmptyState
          emoji="📭"
          title="Nothing sent yet"
          hint="Once the agent sends its first email, every day appears here with what went out and what did not."
        />
      ) : (
        <div className="space-y-4">
          {report.days.map((day) => (
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
        </div>
      )}

      {/* --------------------------------------------------- recycle bin */}
      <Card>
        <div className="mb-3 flex items-center gap-2.5">
          <Inbox size={17} className="text-latte/50" />
          <div>
            <h2 className="font-display text-lg text-latte">Recycle bin</h2>
            <p className="text-[11px] text-latte/45">
              Deleted campaigns. The emails they sent stay in the report above, whatever happens
              here.
            </p>
          </div>
        </div>
        {binned.length === 0 ? (
          <p className="py-4 text-center text-sm text-latte/35">Nothing deleted.</p>
        ) : (
          <div className="space-y-2">
            {binned.map((c) => (
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
          </div>
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

function Figure({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <div>
      <p className={`font-body text-2xl font-semibold ${tone ?? 'text-latte'}`}>{value}</p>
      <p className="text-[10.5px] uppercase tracking-wider text-latte/45">{label}</p>
    </div>
  )
}
