import { Bell, Check, Sparkles, Trash2, Wand2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  PriorityBadge,
  Skeleton,
  StatusBadge,
} from '../components/ui'
import { api } from '../lib/api'
import { relativeDays } from '../lib/format'
import { useToast } from '../lib/toast'
import type { Reminder, Suggestion } from '../lib/types'

export function Reminders() {
  const toast = useToast()
  const [reminders, setReminders] = useState<Reminder[]>([])
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [aiModel, setAiModel] = useState('')
  const [aiEnabled, setAiEnabled] = useState(true)
  const [loading, setLoading] = useState(true)
  const [loadingAi, setLoadingAi] = useState(true)
  const [applying, setApplying] = useState(false)
  const [showDone, setShowDone] = useState(false)
  const [deleting, setDeleting] = useState<Reminder | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setReminders(await api.listReminders({ include_done: showDone }))
    } catch {
      toast.error('Could not load reminders.')
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showDone])

  const loadAi = useCallback(async () => {
    setLoadingAi(true)
    try {
      const res = await api.suggestions()
      setSuggestions(res.suggestions)
      setAiModel(res.model)
      setAiEnabled(res.ai_enabled)
    } catch {
      setSuggestions([])
    } finally {
      setLoadingAi(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    void loadAi()
  }, [loadAi])

  const toggle = async (r: Reminder) => {
    const next = !r.is_done
    setReminders((list) => list.map((x) => (x.id === r.id ? { ...x, is_done: next } : x)))
    try {
      await api.updateReminder(r.id, { is_done: next })
      if (next) toast.success('☕ Follow-up cleared.')
    } catch {
      setReminders((list) => list.map((x) => (x.id === r.id ? { ...x, is_done: !next } : x)))
      toast.error('Could not update the reminder.')
    }
  }

  const remove = async () => {
    if (!deleting) return
    try {
      await api.deleteReminder(deleting.id)
      setReminders((list) => list.filter((x) => x.id !== deleting.id))
      toast.success('Reminder removed.')
    } catch {
      toast.error('Could not delete the reminder.')
    } finally {
      setDeleting(null)
    }
  }

  const applyAll = async () => {
    setApplying(true)
    try {
      const created = await api.applySuggestions()
      toast.success(
        created.length
          ? `⏰ ${created.length} follow-up${created.length === 1 ? '' : 's'} added to your list.`
          : 'All suggested follow-ups are already on your list.',
      )
      await load()
    } catch {
      toast.error('Could not create the reminders.')
    } finally {
      setApplying(false)
    }
  }

  const overdue = reminders.filter(
    (r) => !r.is_done && new Date(r.due_date) < new Date(new Date().toDateString()),
  )

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl text-latte">Follow-ups</h1>
          <p className="mt-1 text-sm text-latte/50">
            {overdue.length > 0 ? (
              <span className="text-red-300">
                {overdue.length} overdue · {reminders.filter((r) => !r.is_done).length} open
              </span>
            ) : (
              `${reminders.filter((r) => !r.is_done).length} open`
            )}
          </p>
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-sm text-latte/55">
          <input
            type="checkbox"
            checked={showDone}
            onChange={(e) => setShowDone(e.target.checked)}
            className="h-4 w-4 accent-[#D9A05B]"
          />
          Show completed
        </label>
      </div>

      {/* --------------------------------------------- AI suggestions */}
      <Card className="border-gold/25 bg-gold/[0.05]">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <Sparkles size={18} className="text-gold" />
            <div>
              <h2 className="font-display text-lg text-latte">Smart Follow-up Suggestions</h2>
              <p className="text-[11px] text-latte/45">
                {aiModel ? `Ranked by ${aiModel}` : 'Claude Haiku'}
              </p>
            </div>
          </div>
          {suggestions.length > 0 && (
            <Button
              onClick={applyAll}
              loading={applying}
              icon={<Wand2 size={14} />}
              className="px-3.5 py-2 text-xs"
            >
              Add all to my list
            </Button>
          )}
        </div>

        {loadingAi ? (
          <div className="space-y-2.5">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : suggestions.length === 0 ? (
          <p className="py-6 text-center text-sm text-latte/45">
            Nothing needs chasing right now — every account has been contacted recently.
          </p>
        ) : (
          <ul className="space-y-2.5">
            {suggestions.map((s) => (
              <li
                key={s.contact_id}
                className="rounded-xl border border-caramel/15 bg-bean/35 px-4 py-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <PriorityBadge priority={s.priority} />
                  <Link
                    to={`/app/trade/quotes/${s.contact_id}`}
                    className="text-sm font-semibold text-latte hover:text-gold"
                  >
                    {s.company_name}
                  </Link>
                  <span className="text-[11px] text-latte/40">{s.country}</span>
                  <StatusBadge status={s.status} />
                  {s.days_since_contact !== null && (
                    <span className="text-[11px] text-latte/35">
                      {s.days_since_contact}d silent
                    </span>
                  )}
                </div>
                <p className="mt-2 text-sm text-latte/65">{s.reason}</p>
                <p className="mt-1.5 flex items-start gap-1.5 text-sm text-gold/85">
                  <span aria-hidden>→</span>
                  {s.suggested_action}
                </p>
              </li>
            ))}
          </ul>
        )}

        {!loadingAi && !aiEnabled && (
          <p className="mt-4 rounded-lg border border-caramel/20 bg-bean/40 px-3 py-2 text-[11px] text-latte/45">
            Ranked with built-in rules. Set <code className="text-gold">ANTHROPIC_API_KEY</code> on
            the backend for Claude Haiku reasoning.
          </p>
        )}
      </Card>

      {/* ------------------------------------------------ reminder list */}
      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : reminders.length === 0 ? (
        <EmptyState
          emoji="🫖"
          title="Your follow-up cup is empty"
          hint="Set a next follow-up date when logging an interaction, or apply an AI suggestion above."
        />
      ) : (
        <Card className="!p-0">
          <ul className="divide-y divide-caramel/10">
            {reminders.map((r) => {
              const isOverdue =
                !r.is_done && new Date(r.due_date) < new Date(new Date().toDateString())
              return (
                <li key={r.id} className="flex items-start gap-3 px-5 py-4">
                  <button
                    onClick={() => toggle(r)}
                    className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border transition ${
                      r.is_done
                        ? 'border-emerald-400/60 bg-emerald-400/20 text-emerald-300'
                        : 'border-caramel/35 hover:border-gold'
                    }`}
                    aria-label={r.is_done ? 'Mark as open' : 'Mark as done'}
                  >
                    {r.is_done && <Check size={12} />}
                  </button>

                  <div className="min-w-0 flex-1">
                    <p
                      className={`text-sm ${r.is_done ? 'text-latte/35 line-through' : 'text-latte/85'}`}
                    >
                      {r.message}
                    </p>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px]">
                      <Link
                        to={`/app/trade/quotes/${r.contact_id}`}
                        className="text-latte/50 hover:text-gold"
                      >
                        {r.contact_company ?? `Account #${r.contact_id}`}
                      </Link>
                      <span className={isOverdue ? 'text-red-300' : 'text-latte/40'}>
                        · {relativeDays(r.due_date)}
                      </span>
                      {r.source === 'ai' && (
                        <span className="inline-flex items-center gap-1 text-gold/60">
                          <Sparkles size={9} /> AI
                        </span>
                      )}
                    </div>
                  </div>

                  <PriorityBadge priority={r.priority} />

                  <button
                    onClick={() => setDeleting(r)}
                    className="rounded-lg p-1.5 text-latte/35 transition hover:bg-red-500/15 hover:text-red-300"
                    aria-label="Delete reminder"
                  >
                    <Trash2 size={14} />
                  </button>
                </li>
              )
            })}
          </ul>
        </Card>
      )}

      <ConfirmDialog
        open={!!deleting}
        title="Delete this reminder?"
        message="The follow-up will be removed from your list."
        onConfirm={remove}
        onCancel={() => setDeleting(null)}
      />

      {reminders.length === 0 && !loading && (
        <p className="flex items-center justify-center gap-2 text-center text-xs text-latte/25">
          <Bell size={12} /> Reminders appear here when you set a next follow-up date.
        </p>
      )}
    </div>
  )
}
