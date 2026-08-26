/**
 * One campaign: what it has done, what it is about to do, and every send it
 * attempted — successes and failures side by side, because a list of only the
 * successes is how you come to believe a campaign went better than it did.
 */
import { ArrowLeft, Check, RefreshCw, SkipForward } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { Button, Card, EmptyState, Skeleton } from '../components/ui'
import { ApiError, api } from '../lib/api'
import { formatDateTime } from '../lib/format'
import { useToast } from '../lib/toast'
import type { CampaignEvent, CampaignStatus, CampaignTarget, SendAttempt } from '../lib/types'

const ATTEMPT_TONE: Record<string, string> = {
  sent: 'text-emerald-300',
  failed: 'text-red-300',
  invalid_email: 'text-red-300',
  auth_error: 'text-red-300',
  duplicate_skipped: 'text-latte/50',
  daily_limit: 'text-gold',
  unverified: 'text-gold',
}

interface DuplicateWarning {
  targetId: number
  reason: string | null
  companySeen: string | null
  userConfirmed: boolean
}

export function CampaignDetail() {
  const { id } = useParams()
  const campaignId = Number(id)
  const toast = useToast()

  const [status, setStatus] = useState<CampaignStatus | null>(null)
  const [drafts, setDrafts] = useState<CampaignTarget[]>([])
  const [attempts, setAttempts] = useState<SendAttempt[]>([])
  const [events, setEvents] = useState<CampaignEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState<number | null>(null)
  const [duplicateWarning, setDuplicateWarning] = useState<DuplicateWarning | null>(null)

  const load = useCallback(async () => {
    try {
      const [s, d, a, e] = await Promise.all([
        api.campaignStatus(campaignId),
        api.campaignQueue(campaignId, { state: 'awaiting_approval', limit: 20 }),
        api.campaignAttempts(campaignId, 50),
        api.campaignEvents(campaignId, 20),
      ])
      setStatus(s)
      setDrafts(d)
      setAttempts(a)
      setEvents(e)
    } catch {
      toast.error('Could not load this campaign.')
    } finally {
      setLoading(false)
    }
  }, [campaignId, toast])

  useEffect(() => {
    void load()
  }, [load])

  const approve = async (target: CampaignTarget, confirmed = false) => {
    if (!confirmed) {
      setActing(target.id)
      try {
        const check = await api.checkTargetDuplicates(campaignId, target.id)
        if (check.is_duplicate) {
          setDuplicateWarning({
            targetId: target.id,
            reason: check.reason,
            companySeen: check.company_seen_before,
            userConfirmed: false,
          })
          setActing(null)
          return
        }
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : 'Could not check that email.')
        setActing(null)
        return
      }
    }

    setActing(target.id)
    try {
      const result = await api.approveTarget(campaignId, target.id, confirmed)
      toast.success(result.steps[0]?.message ?? 'Sent.')
      await load()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not send that one.')
    } finally {
      setActing(null)
      setDuplicateWarning(null)
    }
  }

  const skip = async (target: CampaignTarget) => {
    setActing(target.id)
    try {
      await api.skipTarget(campaignId, target.id, 'Skipped by hand')
      await load()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not skip that one.')
    } finally {
      setActing(null)
    }
  }

  const retry = async (targetId: number) => {
    try {
      await api.retryTarget(campaignId, targetId)
      toast.success('Back in the queue.')
      await load()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not retry.')
    }
  }

  if (loading) return <Skeleton className="h-96" />
  if (!status) return <EmptyState emoji="📭" title="Campaign not found" />

  return (
    <div className="space-y-6">
      {/* ------- Duplicate warning dialog ------- */}
      {duplicateWarning && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <Card className="max-w-md">
            <h3 className="font-display text-lg text-latte">Email already sent</h3>
            <p className="mt-2 text-sm text-latte/75">
              {duplicateWarning.reason || 'This address has already received an email from us.'}
            </p>
            {duplicateWarning.companySeen && (
              <p className="mt-2 text-xs text-latte/50">
                We have also worked with this company before.
              </p>
            )}
            <div className="mt-4 flex items-center gap-2">
              <input
                type="checkbox"
                id="dup-confirm"
                checked={duplicateWarning.userConfirmed}
                onChange={(e) => {
                  setDuplicateWarning({ ...duplicateWarning, userConfirmed: e.target.checked })
                }}
                className="h-4 w-4 cursor-pointer rounded border border-caramel/20 bg-bean/50 accent-gold"
              />
              <label htmlFor="dup-confirm" className="cursor-pointer text-sm text-latte/70">
                It's ok, I know. Send anyway.
              </label>
            </div>
            <div className="mt-5 flex gap-3">
              <Button
                variant="ghost"
                onClick={() => setDuplicateWarning(null)}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                onClick={() => {
                  if (duplicateWarning) {
                    const target = drafts.find((d) => d.id === duplicateWarning.targetId)
                    if (target) {
                      void approve(target, true)
                    }
                  }
                }}
                disabled={!duplicateWarning.userConfirmed}
                loading={acting === duplicateWarning.targetId}
                className="flex-1"
              >
                Send
              </Button>
            </div>
          </Card>
        </div>
      )}
      <div>
        <Link
          to="/app/outreach/campaigns"
          className="inline-flex items-center gap-1.5 text-xs text-latte/50 hover:text-gold"
        >
          <ArrowLeft size={13} /> All campaigns
        </Link>
        <h1 className="mt-2 font-display text-3xl text-latte">{status.name}</h1>
      </div>

      {/* --------------------------------------------------------- summary */}
      <Card>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <Figure label="Sent" value={status.sent} tone="text-emerald-300" />
          <Figure label="Companies" value={status.companies_contacted} />
          <Figure label="Duplicates" value={status.duplicates} />
          <Figure label="Failed" value={status.failed} tone={status.failed ? 'text-red-300' : undefined} />
          <Figure label="Skipped" value={status.skipped} />
          <Figure label="Remaining" value={status.remaining} />
        </div>

        <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-latte/10">
          <div
            className="h-full rounded-full bg-gold transition-[width] duration-500"
            style={{ width: `${status.percent}%` }}
          />
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1 text-[11.5px] text-latte/45">
          <span>
            {status.processed} of {status.total} processed ({status.percent}%)
          </span>
          <span>
            Today {status.sent_today} / {status.daily_limit}
          </span>
          {status.next_company && <span>Next: {status.next_company}</span>}
          {status.unverified > 0 && (
            <span className="text-gold">{status.unverified} unconfirmed — check Sent folder</span>
          )}
        </div>
      </Card>

      {/* ------------------------------------------------------- approvals */}
      {drafts.length > 0 && (
        <Card>
          <h2 className="font-display text-lg text-latte">
            Waiting for you ({status.awaiting_approval})
          </h2>
          <p className="mb-4 text-[11px] text-latte/45">
            Read one, send it, and the next is prepared. Nothing goes out until you press Send.
          </p>
          <div className="space-y-3">
            {drafts.map((d) => (
              <div key={d.id} className="rounded-xl border border-caramel/15 bg-bean/30 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-medium text-latte">{d.company_name}</p>
                    <p className="text-[11px] text-latte/45">
                      {d.email}
                      {d.country ? ` · ${d.country}` : ''}
                    </p>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <Button
                      onClick={() => approve(d)}
                      loading={acting === d.id}
                      icon={<Check size={14} />}
                      className="px-3 py-1.5 text-xs"
                    >
                      Send
                    </Button>
                    <Button
                      variant="ghost"
                      onClick={() => skip(d)}
                      icon={<SkipForward size={14} />}
                      className="px-3 py-1.5 text-xs"
                    >
                      Skip
                    </Button>
                  </div>
                </div>
                <p className="mt-3 text-[12px] font-medium text-latte/70">{d.prepared_subject}</p>
                <pre className="mt-1.5 max-h-56 overflow-y-auto whitespace-pre-wrap font-body text-[12px] leading-relaxed text-latte/60">
                  {d.prepared_body}
                </pre>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ---------------------------------------------------- send status */}
      <Card className="!p-0">
        <div className="border-b border-caramel/15 p-5 pb-4">
          <h2 className="font-display text-lg text-latte">Email sending status</h2>
          <p className="text-[11px] text-latte/45">
            Every attempt, in order. “Sent” means your mail server accepted it — a bounce arrives in
            your inbox minutes later.
          </p>
        </div>
        {attempts.length === 0 ? (
          <p className="p-8 text-center text-sm text-latte/40">Nothing attempted yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b border-caramel/15">
                <tr>
                  <th className="table-head">Company</th>
                  <th className="table-head">Address</th>
                  <th className="table-head">When</th>
                  <th className="table-head">Result</th>
                  <th className="table-head" />
                </tr>
              </thead>
              <tbody>
                {attempts.map((a) => (
                  <tr key={a.id} className="border-b border-caramel/8">
                    <td className="table-cell">{a.company_name ?? '—'}</td>
                    <td className="table-cell text-[12px] text-latte/60">{a.to_email}</td>
                    <td className="table-cell text-[11px] text-latte/45">
                      {formatDateTime(a.started_at)}
                    </td>
                    <td className="table-cell">
                      <span className={`text-[12px] ${ATTEMPT_TONE[a.status] ?? 'text-latte/60'}`}>
                        {a.status.replace(/_/g, ' ')}
                      </span>
                      {a.error && (
                        <p className="mt-0.5 max-w-md text-[11px] text-latte/40">{a.error}</p>
                      )}
                    </td>
                    <td className="table-cell">
                      {['failed', 'invalid_email'].includes(a.status) && (
                        <button
                          onClick={() => retry(a.target_id)}
                          className="rounded-lg p-1.5 text-latte/40 hover:text-gold"
                          title="Put back in the queue"
                          aria-label={`Retry ${a.company_name ?? a.to_email}`}
                        >
                          <RefreshCw size={13} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* ------------------------------------------------------- the log */}
      <Card>
        <h2 className="mb-3 font-display text-lg text-latte">Activity</h2>
        {events.length === 0 ? (
          <p className="py-4 text-center text-sm text-latte/40">Nothing logged yet.</p>
        ) : (
          <ol className="relative space-y-3 border-l border-caramel/20 pl-5">
            {events.map((e) => (
              <li key={e.id} className="relative">
                <span className="absolute -left-[26px] top-1.5 h-3 w-3 rounded-full border-2 border-espresso bg-gold" />
                <p className="text-[12.5px] text-latte/75">{e.message}</p>
                <p className="text-[11px] text-latte/35">{formatDateTime(e.at)}</p>
              </li>
            ))}
          </ol>
        )}
      </Card>
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
