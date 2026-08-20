/**
 * The outreach agent: upload a list, press Start, watch it work.
 *
 * Start hands the campaign to the server and this page becomes a window onto
 * it. The sending runs in the backend scheduler, so closing the browser — or
 * the laptop — does not stop it; the queue, the daily count and the position
 * all live in the database, and the campaign carries on from wherever it was.
 */
import { FileUp, Pause, Play, Square } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { OutreachChat } from '../components/OutreachChat'
import { Button, Card, EmptyState, Field, Input, Modal, Select, Skeleton } from '../components/ui'
import { ApiError, api } from '../lib/api'
import { relativeDays } from '../lib/format'
import { useToast } from '../lib/toast'
import type { Campaign, EmailTemplate, ImportReport } from '../lib/types'

export function Campaigns() {
  const toast = useToast()
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [templates, setTemplates] = useState<EmailTemplate[]>([])
  const [mailboxReady, setMailboxReady] = useState<boolean | null>(null)
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [list, tpls, acct] = await Promise.all([
        api.listCampaigns(),
        api.listTemplates().catch(() => []),
        api.emailAccount().catch(() => null),
      ])
      setCampaigns(list)
      setTemplates(tpls)
      setMailboxReady(Boolean(acct?.has_password))
    } catch {
      toast.error('Could not load campaigns.')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    void load()
  }, [load])

  const blocked = mailboxReady === false || templates.length === 0

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl text-latte">Outreach Agent</h1>
          <p className="mt-1 text-sm text-latte/50">
            Upload a company list, and it writes and sends one email at a time — at most{' '}
            <span className="text-latte/70">50 a day</span>.
          </p>
        </div>
        <Button
          onClick={() => setCreating(true)}
          icon={<FileUp size={16} />}
          disabled={blocked}
        >
          New campaign
        </Button>
      </div>

      {blocked && (
        <Card className="!p-4">
          <p className="text-sm text-latte/70">
            Before the first campaign:{' '}
            {mailboxReady === false && (
              <>
                <Link to="/app/outreach/settings" className="text-gold hover:underline">
                  connect your Gmail
                </Link>
                {templates.length === 0 && ' and '}
              </>
            )}
            {templates.length === 0 && (
              <Link to="/app/outreach/settings" className="text-gold hover:underline">
                write your email template
              </Link>
            )}
            .
          </p>
        </Card>
      )}

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : campaigns.length === 0 ? (
        <EmptyState
          emoji="📮"
          title="No campaigns yet"
          hint="Upload a cleaned company file and the agent will work through it, fifty a day, logging every send."
          action={
            !blocked ? (
              <Button onClick={() => setCreating(true)} icon={<FileUp size={16} />}>
                New campaign
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="space-y-3">
          {campaigns.map((c) => (
            <CampaignRow key={c.id} campaign={c} onChanged={load} />
          ))}
        </div>
      )}

      <OutreachChat onActed={load} />

      <ImportModal
        open={creating}
        templates={templates}
        onClose={() => setCreating(false)}
        onDone={() => {
          setCreating(false)
          void load()
        }}
      />
    </div>
  )
}

/* --------------------------------------------------------------- one campaign */

const STATE_META: Record<string, { label: string; hex: string }> = {
  draft: { label: 'Draft', hex: '#9C8AA5' },
  running: { label: 'Running', hex: '#4FD18B' },
  paused: { label: 'Paused', hex: '#E0A458' },
  daily_limit: { label: 'Daily limit reached', hex: '#D9A05B' },
  completed: { label: 'Completed', hex: '#5BA8D9' },
  stopped: { label: 'Stopped', hex: '#D9705B' },
}

function CampaignRow({ campaign, onChanged }: { campaign: Campaign; onChanged: () => void }) {
  const toast = useToast()
  const [status, setStatus] = useState<Awaited<ReturnType<typeof api.campaignStatus>> | null>(null)
  const [switching, setSwitching] = useState(false)

  const refresh = useCallback(async () => {
    try {
      setStatus(await api.campaignStatus(campaign.id))
    } catch {
      /* the row simply keeps its last known numbers */
    }
  }, [campaign.id])

  useEffect(() => {
    void refresh()
  }, [refresh])

  /* The page no longer sends anything.

     It used to drive the queue itself, one request per company, which meant
     closing the tab stopped the campaign. The sending now lives in the server,
     so this only asks how it is going — and stops asking when it is over. */
  useEffect(() => {
    const live = status?.status === 'running'
    if (!live) return
    const id = window.setInterval(() => {
      void api
        .campaignStatus(campaign.id)
        .then((s) => {
          setStatus(s)
          if (s.status !== 'running') onChanged()
        })
        .catch(() => undefined)
    }, 4000)
    return () => window.clearInterval(id)
  }, [status?.status, campaign.id, onChanged])

  const switchMode = async () => {
    const next = mode === 'manual' ? 'automatic' : 'manual'
    setSwitching(true)
    try {
      setStatus(await api.updateCampaign(campaign.id, { mode: next }))
      toast.success(
        next === 'automatic'
          ? 'Sending automatically now, up to 50 a day.'
          : 'Each email will wait for your approval.',
      )
      onChanged()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not change that.')
    } finally {
      setSwitching(false)
    }
  }

  const start = async () => {
    try {
      setStatus(await api.startCampaign(campaign.id))
      toast.success('Running. It keeps going even if you close this page.')
      onChanged()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not start.')
    }
  }

  const pause = async () => {
    try {
      setStatus(await api.pauseCampaign(campaign.id))
      toast.success('Paused. Nothing further will be sent.')
      onChanged()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not pause.')
    }
  }

  const stop = async () => {
    try {
      setStatus(await api.stopCampaign(campaign.id))
      toast.success('Campaign stopped. The record is kept.')
      onChanged()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not stop.')
    }
  }

  const mode = status?.mode ?? campaign.mode
  const meta = STATE_META[status?.status ?? campaign.status] ?? STATE_META.draft
  const percent = status?.percent ?? 0
  const canStart = ['draft', 'paused', 'daily_limit'].includes(status?.status ?? campaign.status)
  const canPause = (status?.status ?? campaign.status) === 'running'
  const finished = ['completed', 'stopped'].includes(status?.status ?? campaign.status)

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to={`/app/outreach/campaigns/${campaign.id}`}
              className="font-medium text-latte hover:text-gold"
            >
              {campaign.name}
            </Link>
            <span
              className="chip"
              style={{ borderColor: `${meta.hex}66`, backgroundColor: `${meta.hex}1f`, color: meta.hex }}
            >
              <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: meta.hex }} />
              {meta.label}
            </span>
            {/* Clickable, because the point of starting in manual is to read
                the first few and then stop reading them. */}
            <button
              onClick={switchMode}
              disabled={switching}
              title={
                mode === 'manual'
                  ? 'Currently showing you each email first — click to send automatically'
                  : 'Currently sending automatically — click to approve each email first'
              }
              className={`chip transition ${
                mode === 'manual'
                  ? 'border-caramel/25 bg-bean/40 text-latte/55 hover:border-gold/40'
                  : 'border-emerald-400/35 bg-emerald-400/10 text-emerald-300 hover:border-emerald-400/60'
              }`}
            >
              {mode === 'manual' ? 'Approve each' : 'Automatic'}
            </button>
          </div>

          {status && (
            <>
              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-latte/55">
                <span>
                  <span className="text-latte/85">{status.processed}</span> / {status.total}{' '}
                  processed
                </span>
                <span>
                  <span className="text-emerald-300/90">{status.sent}</span> sent to{' '}
                  {status.companies_contacted} companies
                </span>
                {status.duplicates > 0 && <span>{status.duplicates} duplicates</span>}
                {status.failed > 0 && (
                  <span className="text-red-300/90">{status.failed} failed</span>
                )}
                {status.awaiting_approval > 0 && (
                  <span className="text-gold">{status.awaiting_approval} awaiting approval</span>
                )}
              </div>

              {/* progress */}
              <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-latte/10">
                <div
                  className="h-full rounded-full transition-[width] duration-500"
                  style={{ width: `${percent}%`, backgroundColor: meta.hex }}
                />
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-latte/40">
                <span>
                  Today {status.sent_today} / {status.daily_limit}
                </span>
                {status.next_company && <span>Next: {status.next_company}</span>}
                {status.last_company && <span>Last: {status.last_company}</span>}
                {status.last_activity_at && (
                  <span>{relativeDays(status.last_activity_at)}</span>
                )}
              </div>
            </>
          )}

            </div>

        {/* ------------------------------------------------ start / stop */}
        <div className="flex shrink-0 items-center gap-2">
          {canStart && (
            <Button onClick={start} icon={<Play size={15} />} className="px-3 py-2 text-xs">
              {status?.status === 'daily_limit' ? 'Resume' : 'Start'}
            </Button>
          )}
          {canPause && (
            <Button
              variant="ghost"
              onClick={pause}
              icon={<Pause size={15} />}
              className="px-3 py-2 text-xs"
            >
              Pause
            </Button>
          )}
          {!finished && (
            <button
              onClick={stop}
              title="Stop for good — remaining companies are cancelled"
              aria-label="Stop campaign"
              className="rounded-lg p-2 text-latte/40 transition hover:bg-red-500/15 hover:text-red-300"
            >
              <Square size={15} />
            </button>
          )}
        </div>
      </div>

      {status?.status === 'daily_limit' && (
        <p className="mt-3 rounded-lg border border-gold/25 bg-gold/[0.07] px-3.5 py-2.5 text-[12px] text-latte/70">
          Today’s fifty are spent. It will carry on from{' '}
          <span className="text-gold">{status.next_company}</span> tomorrow — press Resume then, or
          leave it and press Resume whenever you next open this.
        </p>
      )}
    </Card>
  )
}

/* -------------------------------------------------------------------- import */

function ImportModal({
  open,
  templates,
  onClose,
  onDone,
}: {
  open: boolean
  templates: EmailTemplate[]
  onClose: () => void
  onDone: () => void
}) {
  const toast = useToast()
  const [name, setName] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [templateId, setTemplateId] = useState('')
  const [mode, setMode] = useState('manual')
  const [busy, setBusy] = useState(false)
  const [report, setReport] = useState<ImportReport | null>(null)

  useEffect(() => {
    if (open) {
      setName('')
      setFile(null)
      setTemplateId(templates[0] ? String(templates[0].id) : '')
      setMode('manual')
      setReport(null)
    }
  }, [open, templates])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) return toast.error('Choose a CSV or XLSX file.')
    setBusy(true)
    try {
      const form = new FormData()
      form.append('file', file)
      form.append('name', name.trim() || file.name.replace(/\.[^.]+$/, ''))
      if (templateId) form.append('template_id', templateId)
      form.append('mode', mode)
      form.append('daily_limit', '50')
      const result = await api.importCampaign(form)
      setReport(result.report)
      toast.success(`${result.report.addresses} addresses queued.`)
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not read that file.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New campaign"
      subtitle="Upload your cleaned company list — CSV or XLSX"
      width="max-w-2xl"
    >
      {report ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Addresses" value={report.addresses} />
            <Stat label="Companies" value={report.companies} />
            <Stat label="Duplicates removed" value={report.duplicate_addresses} />
            <Stat label="No email" value={report.without_email} />
          </div>
          {report.multi_address_companies > 0 && (
            <p className="text-[12px] text-latte/60">
              {report.multi_address_companies} compan
              {report.multi_address_companies === 1 ? 'y has' : 'ies have'} more than one mailbox —
              each address gets its own email, and each counts towards the fifty.
            </p>
          )}
          {report.possible_duplicates.length > 0 && (
            <div className="rounded-lg border border-gold/25 bg-gold/[0.07] px-3.5 py-3">
              <p className="text-[12px] font-medium text-gold">
                Possibly the same company, on different domains — both are queued:
              </p>
              <ul className="mt-1.5 space-y-1 text-[11.5px] text-latte/60">
                {report.possible_duplicates.slice(0, 6).map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </div>
          )}
          {report.unmapped_columns.length > 0 && (
            <p className="text-[11px] text-latte/40">
              Columns kept but not recognised: {report.unmapped_columns.join(', ')}
            </p>
          )}
          <Button onClick={onDone}>Done</Button>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <Field label="Campaign name" hint="Left blank, the file name is used">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Japan coffee importers"
            />
          </Field>

          <Field
            label="Company file"
            hint="Excel, CSV, TSV, .xls or .ods — column headings are matched automatically, and a file named wrongly is still read correctly"
          >
            <input
              type="file"
              accept=".csv,.tsv,.txt,.xlsx,.xlsm,.xls,.ods,text/csv,text/plain,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.oasis.opendocument.spreadsheet"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="input-field file:mr-3 file:rounded-lg file:border-0 file:bg-gold/15 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-gold"
            />
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Template">
              <Select
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
                options={[
                  { value: '', label: 'Choose a template…' },
                  ...templates.map((t) => ({ value: String(t.id), label: t.name })),
                ]}
              />
            </Field>
            <Field label="Sending" hint="You can switch to automatic once you trust the drafts">
              <Select
                value={mode}
                onChange={(e) => setMode(e.target.value)}
                options={[
                  { value: 'manual', label: 'Show me each email first' },
                  { value: 'automatic', label: 'Send automatically (50/day)' },
                ]}
              />
            </Field>
          </div>

          <div className="flex gap-3">
            <Button type="submit" loading={busy}>
              Upload and queue
            </Button>
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancel
            </Button>
          </div>
        </form>
      )}
    </Modal>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-caramel/15 bg-bean/30 px-3 py-2.5">
      <p className="font-body text-xl font-semibold text-latte">{value}</p>
      <p className="text-[10.5px] uppercase tracking-wider text-latte/45">{label}</p>
    </div>
  )
}
