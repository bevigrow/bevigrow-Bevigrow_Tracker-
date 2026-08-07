import { Filter, Pencil, Plus, Search, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { ContactForm } from '../components/ContactForm'
import {
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  Input,
  Modal,
  Select,
  Skeleton,
  StatusBadge,
  TradeBadge,
} from '../components/ui'
import { api } from '../lib/api'
import type { ContactFilters } from '../lib/api'
import { STATUS_ORDER, compactMoney, kg, relativeDays, statusLabel } from '../lib/format'
import { useToast } from '../lib/toast'
import type { Contact } from '../lib/types'

export function Contacts() {
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const [contacts, setContacts] = useState<Contact[]>([])
  const [countries, setCountries] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<Contact | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState<Contact | null>(null)

  const [search, setSearch] = useState(params.get('search') ?? '')

  const filters: ContactFilters = {
    search: params.get('search') ?? undefined,
    trade_type: params.get('trade_type') ?? undefined,
    status: params.get('status') ?? undefined,
    country: params.get('country') ?? undefined,
  }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setContacts(await api.listContacts(filters))
    } catch {
      toast.error('Could not load accounts.')
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.toString()])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    api.countries().then(setCountries).catch(() => setCountries([]))
  }, [])

  // Debounce the search box so typing doesn't fire a request per keystroke.
  useEffect(() => {
    const id = window.setTimeout(() => {
      const next = new URLSearchParams(params)
      if (search.trim()) next.set('search', search.trim())
      else next.delete('search')
      if (next.toString() !== params.toString()) setParams(next, { replace: true })
    }, 350)
    return () => window.clearTimeout(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search])

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const clearFilters = () => {
    setSearch('')
    setParams(new URLSearchParams(), { replace: true })
  }

  const remove = async () => {
    if (!deleting) return
    try {
      await api.deleteContact(deleting.id)
      setContacts((c) => c.filter((x) => x.id !== deleting.id))
      toast.success(`${deleting.company_name} removed.`)
    } catch {
      toast.error('Could not delete the account.')
    } finally {
      setDeleting(null)
    }
  }

  const activeFilters = ['trade_type', 'status', 'country', 'search'].filter((k) => params.get(k))

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl text-latte">Quotes &amp; Enquiries</h1>
          <p className="mt-1 text-sm text-latte/50">
            {loading ? 'Loading…' : `${contacts.length} quote${contacts.length === 1 ? '' : 's'}`}
            {activeFilters.length > 0 && ' matching your filters'}
          </p>
        </div>
        <Button onClick={() => setCreating(true)} icon={<Plus size={16} />}>
          New Quote
        </Button>
      </div>

      {/* Filters — one row above the data */}
      <Card className="!p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div className="relative lg:col-span-2">
            <Search
              size={15}
              className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-latte/35"
            />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search company, person, product, port, HS code…"
              className="pl-10"
            />
          </div>
          <Select
            value={params.get('trade_type') ?? ''}
            onChange={(e) => setFilter('trade_type', e.target.value)}
            options={[
              { value: '', label: 'All trade types' },
              { value: 'export', label: 'Export' },
              { value: 'import', label: 'Import' },
            ]}
          />
          <Select
            value={params.get('status') ?? ''}
            onChange={(e) => setFilter('status', e.target.value)}
            options={[
              { value: '', label: 'All statuses' },
              ...STATUS_ORDER.map((s) => ({ value: s, label: statusLabel(s) })),
            ]}
          />
          <Select
            value={params.get('country') ?? ''}
            onChange={(e) => setFilter('country', e.target.value)}
            options={[
              { value: '', label: 'All countries' },
              ...countries.map((c) => ({ value: c, label: c })),
            ]}
          />
        </div>
        {activeFilters.length > 0 && (
          <button
            onClick={clearFilters}
            className="mt-3 inline-flex items-center gap-1.5 text-xs text-gold hover:underline"
          >
            <Filter size={12} />
            Clear {activeFilters.length} filter{activeFilters.length === 1 ? '' : 's'}
          </button>
        )}
      </Card>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : contacts.length === 0 ? (
        <EmptyState
          emoji="🌱"
          title="Let's roast some new business opportunities!"
          hint={
            activeFilters.length
              ? 'No accounts match these filters. Try widening your search.'
              : 'Add your first coffee customer or supplier to get started.'
          }
          action={
            activeFilters.length ? (
              <Button variant="ghost" onClick={clearFilters}>
                Clear filters
              </Button>
            ) : (
              <Button onClick={() => setCreating(true)} icon={<Plus size={16} />}>
                New Quote
              </Button>
            )
          }
        />
      ) : (
        <>
          {/* Desktop table */}
          <Card className="hidden !p-0 lg:block">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="border-b border-caramel/15">
                  <tr>
                    <th className="table-head">Company</th>
                    <th className="table-head">Trade</th>
                    <th className="table-head">Coffee</th>
                    <th className="table-head">Status</th>
                    <th className="table-head text-right">Value</th>
                    <th className="table-head">Follow-up</th>
                    <th className="table-head" />
                  </tr>
                </thead>
                <tbody>
                  {contacts.map((c) => (
                    <tr
                      key={c.id}
                      className="border-b border-caramel/8 transition hover:bg-gold/[0.04]"
                    >
                      <td className="table-cell">
                        <Link to={`/app/contacts/${c.id}`} className="group block">
                          <p className="font-medium text-latte group-hover:text-gold">
                            {c.company_name}
                          </p>
                          <p className="text-[11px] text-latte/45">
                            {c.country}
                            {c.contact_person ? ` · ${c.contact_person}` : ''}
                          </p>
                        </Link>
                      </td>
                      <td className="table-cell">
                        <TradeBadge trade={c.trade_type} />
                      </td>
                      <td className="table-cell">
                        <p className="text-sm text-latte/80">{c.coffee_product ?? '—'}</p>
                        <p className="text-[11px] text-latte/40">{kg(c.quantity_kg)}</p>
                      </td>
                      <td className="table-cell">
                        <StatusBadge status={c.status} />
                      </td>
                      <td className="table-cell text-right tabular-nums">
                        {compactMoney(c.estimated_value_usd)}
                      </td>
                      <td className="table-cell">
                        <span className="text-xs text-latte/60">
                          {c.next_follow_up ? relativeDays(c.next_follow_up) : '—'}
                        </span>
                      </td>
                      <td className="table-cell">
                        <div className="flex justify-end gap-1">
                          <button
                            onClick={() => setEditing(c)}
                            className="rounded-lg p-2 text-latte/45 transition hover:bg-latte/10 hover:text-latte"
                            aria-label={`Edit ${c.company_name}`}
                          >
                            <Pencil size={14} />
                          </button>
                          <button
                            onClick={() => setDeleting(c)}
                            className="rounded-lg p-2 text-latte/45 transition hover:bg-red-500/15 hover:text-red-300"
                            aria-label={`Delete ${c.company_name}`}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Mobile cards */}
          <div className="space-y-3 lg:hidden">
            {contacts.map((c) => (
              <Card key={c.id} ripple>
                <div className="flex items-start justify-between gap-3">
                  <Link to={`/app/contacts/${c.id}`} className="min-w-0 flex-1">
                    <p className="truncate font-medium text-latte">{c.company_name}</p>
                    <p className="text-[11px] text-latte/45">{c.country}</p>
                  </Link>
                  <TradeBadge trade={c.trade_type} />
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <StatusBadge status={c.status} />
                  <span className="text-xs text-latte/50">{c.coffee_product ?? '—'}</span>
                </div>
                <div className="mt-3 flex items-center justify-between border-t border-caramel/12 pt-3">
                  <span className="text-sm tabular-nums text-latte/75">
                    {compactMoney(c.estimated_value_usd)}
                  </span>
                  <div className="flex gap-1">
                    <button
                      onClick={() => setEditing(c)}
                      className="rounded-lg p-2 text-latte/45 hover:text-latte"
                      aria-label="Edit"
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      onClick={() => setDeleting(c)}
                      className="rounded-lg p-2 text-latte/45 hover:text-red-300"
                      aria-label="Delete"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </>
      )}

      <Modal
        open={creating}
        onClose={() => setCreating(false)}
        title="New Quote"
        subtitle="Record an RFQ or enquiry — nothing is mandatory"
        width="max-w-3xl"
      >
        <ContactForm
          onCancel={() => setCreating(false)}
          onSaved={(c) => {
            setContacts((prev) => [c, ...prev])
            setCreating(false)
          }}
        />
      </Modal>

      <Modal
        open={!!editing}
        onClose={() => setEditing(null)}
        title={editing?.company_name ?? ''}
        subtitle="Edit quote details"
        width="max-w-3xl"
      >
        {editing && (
          <ContactForm
            contact={editing}
            onCancel={() => setEditing(null)}
            onSaved={(c) => {
              setContacts((prev) => prev.map((x) => (x.id === c.id ? { ...x, ...c } : x)))
              setEditing(null)
            }}
          />
        )}
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title="Delete this account?"
        message={`${deleting?.company_name} and all of its interactions, documents and reminders will be permanently removed. This cannot be undone.`}
        onConfirm={remove}
        onCancel={() => setDeleting(null)}
      />
    </div>
  )
}
