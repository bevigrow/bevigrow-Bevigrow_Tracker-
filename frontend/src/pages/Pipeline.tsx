import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { Card, EmptyState, Select, Spinner, TradeBadge } from '../components/ui'
import { api } from '../lib/api'
import { STATUS_META, STATUS_ORDER, compactMoney, kg, relativeDays } from '../lib/format'
import { useToast } from '../lib/toast'
import type { Contact, DealStatus } from '../lib/types'

export function Pipeline() {
  const toast = useToast()
  const [board, setBoard] = useState<Record<DealStatus, Contact[]> | null>(null)
  const [loading, setLoading] = useState(true)
  const [tradeType, setTradeType] = useState('')
  const [moving, setMoving] = useState<number | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setBoard(await api.pipeline(tradeType || undefined))
    } catch {
      toast.error('Could not load the pipeline.')
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tradeType])

  useEffect(() => {
    void load()
  }, [load])

  /** Move a deal one stage forward or back. */
  const move = async (contact: Contact, direction: 1 | -1) => {
    // 'rejected' sits at the end of the list but isn't part of the linear flow.
    const flow: DealStatus[] = STATUS_ORDER.filter((s) => s !== 'rejected')
    const flowIdx = flow.indexOf(contact.status)
    if (flowIdx === -1) return
    const nextIdx = flowIdx + direction
    if (nextIdx < 0 || nextIdx >= flow.length) return
    const next = flow[nextIdx]

    setMoving(contact.id)
    try {
      await api.updateContact(contact.id, { status: next })
      setBoard((b) => {
        if (!b) return b
        const copy = { ...b }
        copy[contact.status] = copy[contact.status].filter((c) => c.id !== contact.id)
        copy[next] = [{ ...contact, status: next }, ...copy[next]]
        return copy
      })
      toast.success(`${contact.company_name} → ${STATUS_META[next].label}`)
    } catch {
      toast.error('Could not move that deal.')
    } finally {
      setMoving(null)
    }
  }

  if (loading) return <Spinner label="Arranging the pipeline…" />
  if (!board) return <EmptyState emoji="☕" title="The pipeline could not be loaded" />

  const total = Object.values(board).reduce((n, list) => n + list.length, 0)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl text-latte">Trade Pipeline</h1>
          <p className="mt-1 text-sm text-latte/50">
            {total} account{total === 1 ? '' : 's'} across {STATUS_ORDER.length} stages
          </p>
        </div>
        <div className="w-48">
          <Select
            value={tradeType}
            onChange={(e) => setTradeType(e.target.value)}
            options={[
              { value: '', label: 'Export + Import' },
              { value: 'export', label: 'Export only' },
              { value: 'import', label: 'Import only' },
            ]}
          />
        </div>
      </div>

      {total === 0 ? (
        <EmptyState
          emoji="🌱"
          title="No deals in the pipeline"
          hint="Add an account to see it appear here."
          action={
            <Link to="/app/trade/quotes" className="btn-primary">
              Go to accounts
            </Link>
          }
        />
      ) : (
        <div className="-mx-5 overflow-x-auto px-5 pb-4 lg:-mx-8 lg:px-8">
          <div className="flex gap-4" style={{ minWidth: 'max-content' }}>
            {STATUS_ORDER.map((status) => {
              const list = board[status] ?? []
              const meta = STATUS_META[status]
              const stageValue = list.reduce((n, c) => n + (c.estimated_value_usd ?? 0), 0)
              return (
                <div key={status} className="w-72 shrink-0">
                  <div
                    className="mb-3 rounded-xl border px-3.5 py-2.5"
                    style={{ borderColor: `${meta.hex}44`, background: `${meta.hex}12` }}
                  >
                    <div className="flex items-center justify-between">
                      <span
                        className="text-xs font-semibold uppercase tracking-wide"
                        style={{ color: meta.hex }}
                      >
                        {meta.label}
                      </span>
                      <span className="rounded-full bg-bean/50 px-2 py-0.5 text-[11px] font-semibold tabular-nums text-latte/70">
                        {list.length}
                      </span>
                    </div>
                    {stageValue > 0 && (
                      <p className="mt-1 text-[11px] tabular-nums text-latte/45">
                        {compactMoney(stageValue)}
                      </p>
                    )}
                  </div>

                  <div className="space-y-2.5">
                    {list.map((c) => (
                      <Card key={c.id} ripple className="!p-3.5">
                        <Link to={`/app/trade/quotes/${c.id}`}>
                          <p className="truncate text-sm font-medium text-latte hover:text-gold">
                            {c.company_name}
                          </p>
                          <p className="text-[11px] text-latte/45">{c.country}</p>
                        </Link>
                        <div className="mt-2 flex flex-wrap items-center gap-1.5">
                          <TradeBadge trade={c.trade_type} />
                        </div>
                        <p className="mt-2 truncate text-[11px] text-latte/50">
                          {c.coffee_product ?? '—'} · {kg(c.quantity_kg)}
                        </p>
                        <div className="mt-2.5 flex items-center justify-between border-t border-caramel/12 pt-2.5">
                          <span className="text-xs tabular-nums text-latte/70">
                            {compactMoney(c.estimated_value_usd)}
                          </span>
                          <div className="flex gap-0.5">
                            {/* min-h/min-w keep the hit area at 24px even though
                                the glyph itself stays small and unobtrusive. */}
                            <button
                              onClick={() => move(c, -1)}
                              disabled={moving === c.id || status === 'new_lead' || status === 'rejected'}
                              className="flex min-h-[24px] min-w-[24px] items-center justify-center rounded text-latte/35 transition hover:bg-latte/10 hover:text-latte disabled:opacity-25"
                              aria-label="Move back one stage"
                            >
                              <ChevronLeft size={14} />
                            </button>
                            <button
                              onClick={() => move(c, 1)}
                              disabled={moving === c.id || status === 'completed' || status === 'rejected'}
                              className="flex min-h-[24px] min-w-[24px] items-center justify-center rounded text-latte/35 transition hover:bg-gold/15 hover:text-gold disabled:opacity-25"
                              aria-label="Move forward one stage"
                            >
                              <ChevronRight size={14} />
                            </button>
                          </div>
                        </div>
                        {c.next_follow_up && (
                          <p className="mt-1.5 text-[10px] text-gold/60">
                            ⏰ {relativeDays(c.next_follow_up)}
                          </p>
                        )}
                      </Card>
                    ))}
                    {list.length === 0 && (
                      <div className="rounded-xl border border-dashed border-caramel/15 py-8 text-center text-[11px] text-latte/25">
                        Empty
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
