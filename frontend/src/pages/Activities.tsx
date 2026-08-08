import { RefreshCw, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { Card, ConfirmDialog, EmptyState, Input, Select, Skeleton } from '../components/ui'
import { api } from '../lib/api'
import { CHANNEL_META, formatDateTime, relativeDays } from '../lib/format'
import { useToast } from '../lib/toast'
import type { Activity, Channel, User } from '../lib/types'

export function Activities() {
  const toast = useToast()
  const [activities, setActivities] = useState<Activity[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [channel, setChannel] = useState('')
  const [userId, setUserId] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [deleting, setDeleting] = useState<Activity | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setActivities(
        await api.listActivities({
          channel: channel || undefined,
          user_id: userId || undefined,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
          limit: 200,
        }),
      )
    } catch {
      toast.error('Could not load the activity log.')
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [channel, userId, dateFrom, dateTo])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    api.listUsers().then(setUsers).catch(() => setUsers([]))
  }, [])

  const resummarize = async (a: Activity) => {
    setBusyId(a.id)
    try {
      const updated = await api.resummarize(a.id)
      setActivities((list) => list.map((x) => (x.id === a.id ? { ...x, ...updated } : x)))
      toast.success('Summary regenerated.')
    } catch {
      toast.error('Could not regenerate the summary.')
    } finally {
      setBusyId(null)
    }
  }

  const remove = async () => {
    if (!deleting) return
    try {
      await api.deleteActivity(deleting.id)
      setActivities((list) => list.filter((x) => x.id !== deleting.id))
      toast.success('Entry removed.')
    } catch {
      toast.error('Could not delete the entry.')
    } finally {
      setDeleting(null)
    }
  }

  const clearFilters = () => {
    setChannel('')
    setUserId('')
    setDateFrom('')
    setDateTo('')
  }

  const hasFilters = channel || userId || dateFrom || dateTo

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl text-latte">Daily Activity Log</h1>
        <p className="mt-1 text-sm text-latte/50">
          {loading ? 'Loading…' : `${activities.length} interaction${activities.length === 1 ? '' : 's'}`}
        </p>
      </div>

      <Card className="!p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Select
            value={channel}
            onChange={(e) => setChannel(e.target.value)}
            options={[
              { value: '', label: 'All channels' },
              ...(Object.keys(CHANNEL_META) as Channel[]).map((c) => ({
                value: c,
                label: `${CHANNEL_META[c].icon}  ${CHANNEL_META[c].label}`,
              })),
            ]}
          />
          <Select
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            options={[
              { value: '', label: 'All employees' },
              ...users.map((u) => ({ value: String(u.id), label: u.name })),
            ]}
          />
          <Input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            aria-label="From date"
          />
          <Input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            aria-label="To date"
          />
        </div>
        {hasFilters && (
          <button onClick={clearFilters} className="mt-3 text-xs text-gold hover:underline">
            Clear filters
          </button>
        )}
      </Card>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : activities.length === 0 ? (
        <EmptyState
          emoji="📋"
          title="No fresh coffee leads brewed today ☕"
          hint={
            hasFilters
              ? 'No entries match these filters.'
              : 'Interactions you log against an account will appear here.'
          }
        />
      ) : (
        <div className="space-y-3">
          {activities.map((a) => (
            <Card key={a.id} ripple>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      to={`/app/trade/quotes/${a.contact_id}`}
                      className="text-sm font-semibold text-latte hover:text-gold"
                    >
                      {a.contact_company ?? `Account #${a.contact_id}`}
                    </Link>
                    <span className="chip border-caramel/25 bg-bean/40 text-latte/55">
                      {CHANNEL_META[a.channel].icon} {CHANNEL_META[a.channel].label}
                    </span>
                    <span className="text-[11px] text-latte/35">
                      {formatDateTime(a.occurred_at)}
                    </span>
                    {a.user && <span className="text-[11px] text-latte/30">· {a.user.name}</span>}
                  </div>

                  {a.ai_summary && (
                    <p className="mt-2.5 rounded-lg border border-gold/20 bg-gold/[0.05] p-3 text-sm leading-relaxed text-latte/80">
                      {a.ai_summary}
                    </p>
                  )}
                  <p className="mt-2 text-sm text-latte/55">{a.discussion}</p>
                  {a.customer_reply && (
                    <p className="mt-1.5 border-l-2 border-caramel/30 pl-3 text-sm italic text-latte/45">
                      Reply: {a.customer_reply}
                    </p>
                  )}
                  {a.next_follow_up && (
                    <p className="mt-2 text-[11px] text-gold/70">
                      ⏰ Follow-up {relativeDays(a.next_follow_up)}
                    </p>
                  )}
                </div>

                <div className="flex gap-1">
                  <button
                    onClick={() => resummarize(a)}
                    disabled={busyId === a.id}
                    className="rounded-lg p-2 text-latte/40 transition hover:bg-latte/10 hover:text-gold disabled:opacity-40"
                    aria-label="Regenerate AI summary"
                    title="Regenerate AI summary"
                  >
                    <RefreshCw size={14} className={busyId === a.id ? 'animate-spin' : ''} />
                  </button>
                  <button
                    onClick={() => setDeleting(a)}
                    className="rounded-lg p-2 text-latte/40 transition hover:bg-red-500/15 hover:text-red-300"
                    aria-label="Delete entry"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <ConfirmDialog
        open={!!deleting}
        title="Delete this log entry?"
        message="The interaction will be permanently removed from the account timeline."
        onConfirm={remove}
        onCancel={() => setDeleting(null)}
      />
    </div>
  )
}
