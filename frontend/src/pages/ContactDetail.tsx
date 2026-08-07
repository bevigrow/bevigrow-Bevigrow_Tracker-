import {
  ArrowLeft,
  Bell,
  Download,
  FileUp,
  Mail,
  MessageSquarePlus,
  Pencil,
  Phone,
  RefreshCw,
  Trash2,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ActivityForm } from '../components/ActivityForm'
import { ContactForm } from '../components/ContactForm'
import {
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  Field,
  Input,
  Modal,
  Select,
  Spinner,
  StatusBadge,
  TradeBadge,
} from '../components/ui'
import { api } from '../lib/api'
import {
  CHANNEL_META,
  DOC_TYPE_LABEL,
  formatDate,
  formatDateTime,
  kg,
  money,
  relativeDays,
  todayISO,
} from '../lib/format'
import { useToast } from '../lib/toast'
import type { ContactDetail as Detail, DocType, DocumentFile } from '../lib/types'

const TABS = ['Timeline', 'Documents', 'Follow-ups'] as const
type Tab = (typeof TABS)[number]

export function ContactDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const toast = useToast()
  const [contact, setContact] = useState<Detail | null>(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<Tab>('Timeline')
  const [logging, setLogging] = useState(false)
  const [editing, setEditing] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [addingReminder, setAddingReminder] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [resummarizing, setResummarizing] = useState<number | null>(null)

  const load = useCallback(async () => {
    if (!id) return
    try {
      setContact(await api.getContact(Number(id)))
    } catch {
      toast.error('Could not load this account.')
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  useEffect(() => {
    void load()
  }, [load])

  const resummarize = async (activityId: number) => {
    setResummarizing(activityId)
    try {
      const updated = await api.resummarize(activityId)
      setContact((c) =>
        c
          ? { ...c, activities: c.activities.map((a) => (a.id === updated.id ? updated : a)) }
          : c,
      )
      toast.success('Summary regenerated.')
    } catch {
      toast.error('Could not regenerate the summary.')
    } finally {
      setResummarizing(null)
    }
  }

  const removeContact = async () => {
    if (!contact) return
    try {
      await api.deleteContact(contact.id)
      toast.success('Account removed.')
      navigate('/app/contacts')
    } catch {
      toast.error('Could not delete the account.')
    }
  }

  if (loading) return <Spinner label="Pouring the account record…" />
  if (!contact) {
    return (
      <EmptyState
        emoji="🔍"
        title="Account not found"
        action={<Link to="/app/contacts" className="btn-primary">Back to accounts</Link>}
      />
    )
  }

  return (
    <div className="space-y-6">
      <Link
        to="/app/contacts"
        className="inline-flex items-center gap-2 text-sm text-latte/50 transition hover:text-latte"
      >
        <ArrowLeft size={15} />
        All accounts
      </Link>

      {/* ---------------------------------------------------------- header */}
      <Card className="relative overflow-hidden">
        <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-gold/10 blur-3xl" />
        <div className="relative flex flex-wrap items-start justify-between gap-5">
          <div className="min-w-0">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <TradeBadge trade={contact.trade_type} />
              <StatusBadge status={contact.status} />
            </div>
            <h1 className="font-display text-3xl text-latte">{contact.company_name}</h1>
            <p className="mt-1 text-sm text-latte/50">
              {contact.country ?? 'Country not given'}
              {contact.contact_person ? ` · ${contact.contact_person}` : ''}
            </p>
            <div className="mt-3 flex flex-wrap gap-4 text-xs text-latte/55">
              {contact.email && (
                <a href={`mailto:${contact.email}`} className="inline-flex items-center gap-1.5 hover:text-gold">
                  <Mail size={13} /> {contact.email}
                </a>
              )}
              {contact.phone && (
                <a href={`tel:${contact.phone}`} className="inline-flex items-center gap-1.5 hover:text-gold">
                  <Phone size={13} /> {contact.phone}
                </a>
              )}
              {contact.whatsapp && (
                <a
                  href={`https://wa.me/${contact.whatsapp.replace(/[^0-9]/g, '')}`}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 hover:text-gold"
                >
                  💬 {contact.whatsapp}
                </a>
              )}
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button onClick={() => setLogging(true)} icon={<MessageSquarePlus size={15} />}>
              Log interaction
            </Button>
            <Button variant="ghost" onClick={() => setEditing(true)} icon={<Pencil size={14} />}>
              Edit
            </Button>
            <Button variant="danger" onClick={() => setDeleting(true)} icon={<Trash2 size={14} />}>
              Delete
            </Button>
          </div>
        </div>

        <div className="mt-6 grid gap-4 border-t border-caramel/15 pt-5 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Coffee product" value={contact.coffee_product ?? '—'} />
          <Stat
            label="Quantity"
            value={contact.quantity_note || kg(contact.quantity_kg)}
          />
          <Stat
            label="Roast / bean"
            value={[contact.roast_preference, contact.bean_type].filter(Boolean).join(' · ') || '—'}
          />
          <Stat label="Estimated value" value={money(contact.estimated_value_usd)} />
          <Stat label="Shipping terms" value={contact.shipping_terms ?? '—'} />
          <Stat label="Destination port" value={contact.destination_port ?? '—'} />
          <Stat label="Payment terms" value={contact.payment_terms ?? '—'} />
          <Stat label="HS code" value={contact.hs_code ?? '—'} />
          <Stat label="Origin preference" value={contact.origin_preference ?? '—'} />
          <Stat label="Sourcing from" value={contact.sourcing_from ?? '—'} />
          <Stat
            label="RFQ source"
            value={[contact.rfq_source, contact.rfq_reference].filter(Boolean).join(' · ') || '—'}
          />
          <Stat label="Owner" value={contact.owner?.name ?? 'Unassigned'} />
          <Stat label="Last contacted" value={relativeDays(contact.last_contacted_at)} />
          <Stat
            label="Next follow-up"
            value={contact.next_follow_up ? relativeDays(contact.next_follow_up) : '—'}
          />
          <Stat label="Added" value={formatDate(contact.created_at)} />
        </div>

        {contact.notes && (
          <p className="mt-5 rounded-xl border border-caramel/15 bg-bean/30 p-4 text-sm leading-relaxed text-latte/65">
            {contact.notes}
          </p>
        )}
      </Card>

      {/* ------------------------------------------------------------ tabs */}
      <div className="flex gap-1 border-b border-caramel/15">
        {TABS.map((t) => {
          const count =
            t === 'Timeline'
              ? contact.activities.length
              : t === 'Documents'
                ? contact.documents.length
                : contact.reminders.filter((r) => !r.is_done).length
          return (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`relative px-4 py-2.5 text-sm font-medium transition ${
                tab === t ? 'text-latte' : 'text-latte/45 hover:text-latte/75'
              }`}
            >
              {t}
              <span className="ml-1.5 text-[11px] text-latte/35">{count}</span>
              {tab === t && (
                <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-gold" />
              )}
            </button>
          )
        })}
      </div>

      {tab === 'Timeline' && (
        <Card>
          {contact.activities.length ? (
            <ol className="relative space-y-6 border-l border-caramel/20 pl-6">
              {contact.activities.map((a) => (
                <li key={a.id} className="relative">
                  <span className="absolute -left-[31px] top-1 flex h-4 w-4 items-center justify-center rounded-full border-2 border-espresso bg-gold text-[8px]">
                    {CHANNEL_META[a.channel].icon}
                  </span>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-latte">
                      {CHANNEL_META[a.channel].label}
                    </span>
                    <span className="text-[11px] text-latte/40">
                      {formatDateTime(a.occurred_at)}
                    </span>
                    {a.user && <span className="text-[11px] text-latte/30">· {a.user.name}</span>}
                  </div>

                  {a.ai_summary && (
                    <div className="mt-2 rounded-lg border border-gold/20 bg-gold/[0.05] p-3">
                      <div className="mb-1 flex items-center justify-between">
                        <span className="text-[10px] uppercase tracking-wider text-gold/70">
                          AI summary
                        </span>
                        <button
                          onClick={() => resummarize(a.id)}
                          disabled={resummarizing === a.id}
                          className="text-latte/40 transition hover:text-gold disabled:opacity-50"
                          aria-label="Regenerate summary"
                        >
                          <RefreshCw
                            size={12}
                            className={resummarizing === a.id ? 'animate-spin' : ''}
                          />
                        </button>
                      </div>
                      <p className="text-sm leading-relaxed text-latte/80">{a.ai_summary}</p>
                    </div>
                  )}

                  <p className="mt-2 text-sm text-latte/60">{a.discussion}</p>
                  {a.customer_reply && (
                    <p className="mt-1.5 border-l-2 border-caramel/30 pl-3 text-sm italic text-latte/50">
                      Reply: {a.customer_reply}
                    </p>
                  )}
                  {a.next_follow_up && (
                    <p className="mt-2 text-[11px] text-gold/70">
                      ⏰ Follow-up {relativeDays(a.next_follow_up)}
                    </p>
                  )}
                </li>
              ))}
            </ol>
          ) : (
            <EmptyState
              emoji="📋"
              title="No interactions logged yet"
              hint="Log the first call, email or meeting with this account."
              action={
                <Button onClick={() => setLogging(true)} icon={<MessageSquarePlus size={15} />}>
                  Log interaction
                </Button>
              }
            />
          )}
        </Card>
      )}

      {tab === 'Documents' && (
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-display text-lg text-latte">Proof &amp; Documents</h3>
            <Button onClick={() => setUploading(true)} icon={<FileUp size={15} />}>
              Upload
            </Button>
          </div>
          {contact.documents.length ? (
            <DocumentList
              documents={contact.documents}
              onDeleted={(docId) =>
                setContact((c) =>
                  c ? { ...c, documents: c.documents.filter((d) => d.id !== docId) } : c,
                )
              }
            />
          ) : (
            <EmptyState
              emoji="📄"
              title="No proof uploaded yet"
              hint="Attach quotations, invoices, purchase orders or sample photos."
            />
          )}
        </Card>
      )}

      {tab === 'Follow-ups' && (
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-display text-lg text-latte">Follow-up Reminders</h3>
            <Button onClick={() => setAddingReminder(true)} icon={<Bell size={15} />}>
              Add reminder
            </Button>
          </div>
          {contact.reminders.length ? (
            <ul className="space-y-2.5">
              {contact.reminders.map((r) => (
                <li
                  key={r.id}
                  className="flex items-start gap-3 rounded-xl border border-caramel/12 bg-bean/30 px-4 py-3"
                >
                  <input
                    type="checkbox"
                    checked={r.is_done}
                    onChange={async (e) => {
                      const done = e.target.checked
                      await api.updateReminder(r.id, { is_done: done })
                      setContact((c) =>
                        c
                          ? {
                              ...c,
                              reminders: c.reminders.map((x) =>
                                x.id === r.id ? { ...x, is_done: done } : x,
                              ),
                            }
                          : c,
                      )
                    }}
                    className="mt-1 h-4 w-4 accent-[#D9A05B]"
                  />
                  <div className="min-w-0 flex-1">
                    <p
                      className={`text-sm ${r.is_done ? 'text-latte/35 line-through' : 'text-latte/85'}`}
                    >
                      {r.message}
                    </p>
                    <p className="mt-0.5 text-[11px] text-latte/40">
                      {relativeDays(r.due_date)} · {r.priority} priority
                      {r.source === 'ai' && ' · AI suggested'}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState emoji="🫖" title="Your follow-up cup is empty" />
          )}
        </Card>
      )}

      {/* --------------------------------------------------------- modals */}
      <Modal
        open={logging}
        onClose={() => setLogging(false)}
        title="Log an interaction"
        subtitle={contact.company_name}
        width="max-w-2xl"
      >
        <ActivityForm
          contact={contact}
          onCancel={() => setLogging(false)}
          onSaved={() => {
            setLogging(false)
            void load()
          }}
        />
      </Modal>

      <Modal
        open={editing}
        onClose={() => setEditing(false)}
        title="Edit account"
        subtitle={contact.company_name}
        width="max-w-3xl"
      >
        <ContactForm
          contact={contact}
          onCancel={() => setEditing(false)}
          onSaved={() => {
            setEditing(false)
            void load()
          }}
        />
      </Modal>

      <UploadModal
        open={uploading}
        contactId={contact.id}
        onClose={() => setUploading(false)}
        onUploaded={() => {
          setUploading(false)
          void load()
        }}
      />

      <ReminderModal
        open={addingReminder}
        contactId={contact.id}
        onClose={() => setAddingReminder(false)}
        onSaved={() => {
          setAddingReminder(false)
          void load()
        }}
      />

      <ConfirmDialog
        open={deleting}
        title="Delete this account?"
        message={`${contact.company_name} and all of its interactions, documents and reminders will be permanently removed.`}
        onConfirm={removeContact}
        onCancel={() => setDeleting(false)}
      />
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wider text-latte/40">{label}</p>
      <p className="mt-1 text-sm text-latte/85">{value}</p>
    </div>
  )
}

/* ---------------------------------------------------------- document list */

export function DocumentList({
  documents,
  onDeleted,
  showContact = false,
}: {
  documents: DocumentFile[]
  onDeleted: (id: number) => void
  showContact?: boolean
}) {
  const toast = useToast()
  const [removing, setRemoving] = useState<DocumentFile | null>(null)

  const download = async (doc: DocumentFile) => {
    try {
      await api.downloadDocument(doc)
    } catch {
      toast.error('Could not download that file.')
    }
  }

  const confirmRemove = async () => {
    if (!removing) return
    try {
      await api.deleteDocument(removing.id)
      onDeleted(removing.id)
      toast.success('Document removed.')
    } catch {
      toast.error('Could not delete the document.')
    } finally {
      setRemoving(null)
    }
  }

  return (
    <>
      <ul className="grid gap-3 sm:grid-cols-2">
        {documents.map((d) => (
          <li
            key={d.id}
            className="flex items-start gap-3 rounded-xl border border-caramel/15 bg-bean/30 p-4"
          >
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gold/12 text-lg">
              {d.content_type?.startsWith('image/') ? '🖼️' : '📄'}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-latte">{d.original_name}</p>
              <p className="text-[11px] text-latte/45">
                {DOC_TYPE_LABEL[d.doc_type]} · {(d.size_bytes / 1024).toFixed(0)} KB
              </p>
              {showContact && (
                <p className="text-[11px] text-latte/35">Account #{d.contact_id}</p>
              )}
              {d.note && <p className="mt-1 text-[11px] italic text-latte/40">{d.note}</p>}
              <p className="mt-1 text-[10px] text-latte/30">{formatDate(d.created_at)}</p>
            </div>
            <div className="flex shrink-0 flex-col gap-1">
              <button
                onClick={() => download(d)}
                className="rounded-lg p-1.5 text-latte/45 transition hover:bg-latte/10 hover:text-gold"
                aria-label={`Download ${d.original_name}`}
              >
                <Download size={14} />
              </button>
              <button
                onClick={() => setRemoving(d)}
                className="rounded-lg p-1.5 text-latte/45 transition hover:bg-red-500/15 hover:text-red-300"
                aria-label={`Delete ${d.original_name}`}
              >
                <Trash2 size={14} />
              </button>
            </div>
          </li>
        ))}
      </ul>

      <ConfirmDialog
        open={!!removing}
        title="Delete this document?"
        message={`${removing?.original_name} will be permanently removed from the account.`}
        onConfirm={confirmRemove}
        onCancel={() => setRemoving(null)}
      />
    </>
  )
}

/* --------------------------------------------------------------- uploads */

export function UploadModal({
  open,
  contactId,
  contacts,
  onClose,
  onUploaded,
}: {
  open: boolean
  /** Preselected account. Omit when `contacts` is supplied and the user picks. */
  contactId?: number
  /** When provided, the modal shows an account picker (global upload flow). */
  contacts?: { id: number; company_name: string }[]
  onClose: () => void
  onUploaded: () => void
}) {
  const toast = useToast()
  const [file, setFile] = useState<File | null>(null)
  const [docType, setDocType] = useState<DocType>('quotation')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [target, setTarget] = useState<string>(contactId ? String(contactId) : '')

  useEffect(() => {
    if (contactId) setTarget(String(contactId))
  }, [contactId])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!target) {
      toast.error('Choose the account this document belongs to.')
      return
    }
    if (!file) {
      toast.error('Choose a file to upload.')
      return
    }
    setBusy(true)
    const form = new FormData()
    form.append('contact_id', target)
    form.append('doc_type', docType)
    if (note.trim()) form.append('note', note.trim())
    form.append('file', file)
    try {
      await api.uploadDocument(form)
      toast.success('📎 Document attached to the account.')
      setFile(null)
      setNote('')
      onUploaded()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Upload failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Upload proof" width="max-w-lg">
      <form onSubmit={submit} className="space-y-4">
        {contacts && (
          <Field label="Account *">
            <Select
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              options={[
                { value: '', label: 'Choose an account…' },
                ...contacts.map((c) => ({ value: String(c.id), label: c.company_name })),
              ]}
            />
          </Field>
        )}

        <Field label="Document type">
          <Select
            value={docType}
            onChange={(e) => setDocType(e.target.value as DocType)}
            options={(Object.keys(DOC_TYPE_LABEL) as DocType[]).map((t) => ({
              value: t,
              label: DOC_TYPE_LABEL[t],
            }))}
          />
        </Field>

        <Field label="File" hint="PDF, image, Word, Excel or CSV · max 15 MB">
          <label className="flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-caramel/35 bg-bean/25 px-6 py-8 text-center transition hover:border-gold/50">
            <FileUp size={22} className="mb-2 text-gold/70" />
            <span className="text-sm text-latte/70">
              {file ? file.name : 'Click to choose a file'}
            </span>
            {file && (
              <span className="mt-1 text-[11px] text-latte/40">
                {(file.size / 1024).toFixed(0)} KB
              </span>
            )}
            <input
              type="file"
              className="hidden"
              accept=".pdf,.png,.jpg,.jpeg,.webp,.gif,.doc,.docx,.xls,.xlsx,.csv,.txt"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
        </Field>

        <Field label="Note">
          <Input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Quotation Q-1001, valid 30 days"
          />
        </Field>

        <div className="flex justify-end gap-3 border-t border-caramel/15 pt-4">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={busy}>
            Upload
          </Button>
        </div>
      </form>
    </Modal>
  )
}

/* ------------------------------------------------------------- reminders */

function ReminderModal({
  open,
  contactId,
  onClose,
  onSaved,
}: {
  open: boolean
  contactId: number
  onClose: () => void
  onSaved: () => void
}) {
  const toast = useToast()
  const [dueDate, setDueDate] = useState(todayISO())
  const [message, setMessage] = useState('')
  const [priority, setPriority] = useState('medium')
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!message.trim()) {
      toast.error('Describe what needs following up.')
      return
    }
    setBusy(true)
    try {
      await api.createReminder({
        contact_id: contactId,
        due_date: dueDate,
        message: message.trim(),
        priority,
      })
      toast.success('⏰ Reminder set.')
      setMessage('')
      onSaved()
    } catch {
      toast.error('Could not create the reminder.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="New follow-up reminder" width="max-w-lg">
      <form onSubmit={submit} className="space-y-4">
        <Field label="What needs doing?">
          <Input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Chase the Arabica quotation"
          />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Due date">
            <Input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
          </Field>
          <Field label="Priority">
            <Select
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              options={[
                { value: 'high', label: 'High' },
                { value: 'medium', label: 'Medium' },
                { value: 'low', label: 'Low' },
              ]}
            />
          </Field>
        </div>
        <div className="flex justify-end gap-3 border-t border-caramel/15 pt-4">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={busy}>
            Set reminder
          </Button>
        </div>
      </form>
    </Modal>
  )
}
