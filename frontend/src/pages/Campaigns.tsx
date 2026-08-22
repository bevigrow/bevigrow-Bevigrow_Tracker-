/**
 * The outreach agent: upload a list, press Start, watch it work.
 *
 * Start hands the campaign to the server and this page becomes a window onto
 * it. The sending runs in the backend scheduler, so closing the browser — or
 * the laptop — does not stop it; the queue, the daily count and the position
 * all live in the database, and the campaign carries on from wherever it was.
 */
import { FileUp, HelpCircle, MailCheck, Pause, Pencil, Play, Square, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { OutreachChat } from '../components/OutreachChat'
import { OutreachSetup } from '../components/OutreachSetup'
import {
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  Field,
  Input,
  Modal,
  Select,
  Skeleton,
} from '../components/ui'
import { ApiError, api } from '../lib/api'
import { useToast } from '../lib/toast'
import type { Campaign, CampaignStatus, EmailTemplate, ImportReport } from '../lib/types'

export function Campaigns() {
  const toast = useToast()
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [templates, setTemplates] = useState<EmailTemplate[]>([])
  const [mailboxReady, setMailboxReady] = useState<boolean | null>(null)
  const [mailboxVerified, setMailboxVerified] = useState(false)
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  // Opened by hand. The guide appears on its own only when nothing is set
  // up at all; after that it waits behind the Guide button.
  const [guideOpen, setGuideOpen] = useState(false)

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
      // Either credential counts. Checking only the SMTP password told a
      // perfectly configured Resend account to "connect your Gmail" and left
      // New campaign disabled.
      setMailboxReady(Boolean(acct?.has_password || acct?.has_api_key))
      setMailboxVerified(Boolean(acct?.last_verified_at))
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
  // Nothing configured at all — the one case where the guide is the page.
  const fresh = mailboxReady === false && templates.length === 0

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl text-latte">Outreach Agent</h1>
          <p className="mt-1 text-sm text-latte/50">
            Upload a company list and it writes and sends the emails for you — one at a time, at
            most <span className="text-latte/70">50 a day</span>, and it never writes to the same
            address twice.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            onClick={() => setGuideOpen((v) => !v)}
            icon={<HelpCircle size={15} />}
            className="px-3 py-2 text-xs"
          >
            Guide
          </Button>
          <Button
            onClick={() => setCreating(true)}
            icon={<FileUp size={16} />}
            disabled={blocked}
          >
            New campaign
          </Button>
        </div>
      </div>

      {!loading && (guideOpen || fresh) && (
        <OutreachSetup
          state={{
            mailboxReady: Boolean(mailboxReady),
            mailboxVerified,
            hasTemplate: templates.length > 0,
            hasCampaign: campaigns.length > 0,
          }}
          onNewCampaign={() => setCreating(true)}
          onClose={fresh && !guideOpen ? undefined : () => setGuideOpen(false)}
        />
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
  draft: { label: 'Not started', hex: '#9C8AA5' },
  running: { label: 'Sending', hex: '#4FD18B' },
  paused: { label: 'Paused', hex: '#E0A458' },
  daily_limit: { label: "Done for today", hex: '#D9A05B' },
  completed: { label: 'Finished', hex: '#5BA8D9' },
  stopped: { label: 'Stopped', hex: '#D9705B' },
}

/**
 * What is happening, in a sentence.
 *
 * The card used to present six figures and leave the reader to assemble the
 * meaning: "73 / 200 processed", "50/50 today", "next: XYZ". Every one of
 * those is true and none of them answers the question somebody actually opens
 * this page with, which is "is it working, and do I need to do anything?".
 */
function plainState(s: CampaignStatus | null): string {
  if (!s) return 'Loading…'
  const left = s.remaining
  switch (s.status) {
    case 'running':
      // A manual campaign is "running" in the sense that its queue is moving,
      // but nothing leaves until a person presses Send on each draft. Saying
      // "Sending now" while the count sits at zero is the app telling you
      // something it can see is not true, and leaves you waiting for a send
      // that is waiting for you.
      if (s.awaiting_approval > 0)
        return `${s.awaiting_approval} email${
          s.awaiting_approval === 1 ? '' : 's'
        } written and waiting for you to read — open the campaign to send ${
          s.awaiting_approval === 1 ? 'it' : 'them'
        }.`
      return s.next_company
        ? `Sending now — ${s.next_company} is next.`
        : 'Sending now.'
    case 'daily_limit':
      return `Today's ${s.daily_limit} are sent. ${left} still to go — it carries on tomorrow${
        s.next_company ? `, starting with ${s.next_company}` : ''
      }.`
    case 'paused':
      return s.awaiting_approval > 0
        ? `Paused, with ${s.awaiting_approval} email${s.awaiting_approval === 1 ? '' : 's'} waiting for you to read.`
        : `Paused. ${left} still to send whenever you press Start.`
    case 'completed':
      return `Finished — ${s.sent} email${s.sent === 1 ? '' : 's'} to ${s.companies_contacted} compan${
        s.companies_contacted === 1 ? 'y' : 'ies'
      }.`
    case 'stopped':
      return `Stopped. ${s.sent} sent before it was stopped.`
    default:
      return `${s.total} address${s.total === 1 ? '' : 'es'} ready. Press Start when you are.`
  }
}

function CampaignRow({ campaign, onChanged }: { campaign: Campaign; onChanged: () => void }) {
  const toast = useToast()
  const [status, setStatus] = useState<Awaited<ReturnType<typeof api.campaignStatus>> | null>(null)
  const [switching, setSwitching] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)

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

  const remove = async () => {
    try {
      await api.deleteCampaign(campaign.id)
      toast.success('Campaign removed. The emails it sent are still in your outreach log.')
      onChanged()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not delete that.')
    } finally {
      setConfirmingDelete(false)
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
  const [renaming, setRenaming] = useState(false)
  const [draftName, setDraftName] = useState(campaign.name)
  const [busyName, setBusyName] = useState(false)

  const saveName = async (e: React.FormEvent) => {
    e.preventDefault()
    const wanted = draftName.trim()
    if (!wanted || wanted === campaign.name) return setRenaming(false)
    setBusyName(true)
    try {
      await api.updateCampaign(campaign.id, { name: wanted })
      setRenaming(false)
      await onChanged()
      toast.success('Renamed.')
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not rename it.')
    } finally {
      setBusyName(false)
    }
  }

  const finished = ['completed', 'stopped'].includes(status?.status ?? campaign.status)

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {renaming ? (
              /* A campaign is found by its name weeks later, and the name
                 typed at import is usually the filename. Editable whenever,
                 finished ones included — nothing about a name is a record of
                 what happened. */
              <form
                onSubmit={saveName}
                className="flex min-w-0 flex-1 items-center gap-2"
              >
                <Input
                  autoFocus
                  value={draftName}
                  onChange={(e) => setDraftName(e.target.value)}
                  onKeyDown={(e) => e.key === 'Escape' && setRenaming(false)}
                  className="!py-1 text-sm"
                  aria-label="Campaign name"
                />
                <Button type="submit" disabled={busyName} className="!px-2.5 !py-1 text-[12px]">
                  {busyName ? 'Saving…' : 'Save'}
                </Button>
                <button
                  type="button"
                  onClick={() => setRenaming(false)}
                  className="text-[12px] text-latte/40 hover:text-latte/70"
                >
                  Cancel
                </button>
              </form>
            ) : (
              <>
                <Link
                  to={`/app/outreach/campaigns/${campaign.id}`}
                  className="font-medium text-latte hover:text-gold"
                >
                  {campaign.name}
                </Link>
                <button
                  type="button"
                  onClick={() => {
                    setDraftName(campaign.name)
                    setRenaming(true)
                  }}
                  title="Rename this campaign"
                  aria-label={`Rename ${campaign.name}`}
                  className="text-latte/30 transition hover:text-gold"
                >
                  <Pencil size={13} />
                </button>
              </>
            )}
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
              {mode === 'manual' ? 'You read each one first' : 'Sends by itself'}
            </button>
          </div>

          {status && (
            <>
              {/* The one line that answers "is it working?" */}
              <p className="mt-2 text-sm text-latte/80">{plainState(status)}</p>

              <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-latte/10">
                <div
                  className="h-full rounded-full transition-[width] duration-500"
                  style={{ width: `${percent}%`, backgroundColor: meta.hex }}
                />
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11.5px] text-latte/45">
                <span>
                  <span className="text-emerald-300/90">{status.sent}</span> sent
                  {status.companies_contacted > 0 && ` to ${status.companies_contacted} companies`}
                </span>
                <span>{status.remaining} to go</span>
                <span>
                  today {status.sent_today}/{status.daily_limit}
                </span>
                {status.failed > 0 && (
                  <Link
                    to={`/app/outreach/campaigns/${campaign.id}`}
                    className="text-red-300/90 underline decoration-red-300/30 underline-offset-2"
                  >
                    {status.failed} failed
                  </Link>
                )}
                {status.duplicates > 0 && (
                  <span title="Addresses already contacted before, so they were not written to again">
                    {status.duplicates} already contacted
                  </span>
                )}
                {status.awaiting_approval > 0 && (
                  <Link
                    to={`/app/outreach/campaigns/${campaign.id}`}
                    className="text-gold underline decoration-gold/40 underline-offset-2 hover:decoration-gold"
                  >
                    {status.awaiting_approval} waiting for you
                  </Link>
                )}
              </div>
            </>
          )}

            </div>

        {/* ------------------------------------------------ start / stop */}
        <div className="flex shrink-0 items-center gap-2">
          {/* When drafts are waiting, reviewing them is the only thing that
              moves the campaign — so it is the button, ahead of Start. */}
          {(status?.awaiting_approval ?? 0) > 0 && (
            <Link to={`/app/outreach/campaigns/${campaign.id}`}>
              <Button icon={<MailCheck size={15} />} className="px-3 py-2 text-xs">
                Read {status?.awaiting_approval} draft{status?.awaiting_approval === 1 ? '' : 's'}
              </Button>
            </Link>
          )}
          {canStart && (
            <Button onClick={start} icon={<Play size={15} />} className="px-3 py-2 text-xs">
              {status?.status === 'daily_limit'
                ? 'Send more today'
                : status?.status === 'paused'
                  ? 'Continue'
                  : 'Start sending'}
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
          <button
            onClick={() => setConfirmingDelete(true)}
            title="Delete this campaign — sent emails stay in your outreach log"
            aria-label={`Delete ${campaign.name}`}
            className="rounded-lg p-2 text-latte/35 transition hover:bg-red-500/15 hover:text-red-300"
          >
            <Trash2 size={15} />
          </button>
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

      <ConfirmDialog
        open={confirmingDelete}
        title={`Delete “${campaign.name}”?`}
        message={
          `The queue, the drafts and the send history for this campaign are removed. ` +
          `The ${status?.sent ?? 0} email${status?.sent === 1 ? '' : 's'} it actually sent stay ` +
          `in your outreach log — they are the record of real messages, and they are what stops ` +
          `those addresses being written to again.`
        }
        onConfirm={remove}
        onCancel={() => setConfirmingDelete(false)}
      />

      {status?.status === 'daily_limit' && (
        <p className="mt-3 rounded-lg border border-gold/25 bg-gold/[0.07] px-3.5 py-2.5 text-[12px] text-latte/70">
          Nothing more will go out today — that is the fifty-a-day limit doing its job. It picks
          up by itself tomorrow morning; you do not need to be here for it.
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
  const [imported, setImported] = useState<Campaign | null>(null)
  const [starting, setStarting] = useState(false)

  useEffect(() => {
    if (open) {
      setName('')
      setFile(null)
      setTemplateId(templates[0] ? String(templates[0].id) : '')
      setMode('manual')
      setReport(null)
      setImported(null)
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
      setImported(result.campaign)

      // Chosen "send automatically" means send automatically. Making somebody
      // upload a file and then hunt for a Start button is two decisions where
      // they made one, and with a one-row test file it reads as though every
      // single company needs its own press.
      if (mode === 'automatic') {
        try {
          await api.startCampaign(result.campaign.id)
          toast.success(
            `${result.report.addresses} addresses queued — sending has started.`,
          )
        } catch (err) {
          toast.error(
            err instanceof ApiError
              ? err.message
              : 'Queued, but it could not start. Press Start on the campaign.',
          )
        }
      } else {
        toast.success(`${result.report.addresses} addresses queued.`)
      }
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
          {report.repeated_companies.length > 0 && (
            <div className="rounded-lg border border-caramel/25 bg-bean/30 px-3.5 py-3">
              <p className="text-[12px] font-medium text-latte/75">
                The same company appears more than once:
              </p>
              <ul className="mt-1.5 space-y-1 text-[11.5px] text-latte/55">
                {report.repeated_companies.slice(0, 6).map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
              <p className="mt-1.5 text-[11px] text-latte/40">
                All of them are queued. Different addresses at one company are emailed separately;
                the same address twice is never written to twice.
              </p>
            </div>
          )}
          {report.shared_locations.length > 0 && (
            <div className="rounded-lg border border-caramel/25 bg-bean/30 px-3.5 py-3">
              <p className="text-[12px] font-medium text-latte/75">
                Different companies at the same address:
              </p>
              <ul className="mt-1.5 space-y-1 text-[11.5px] text-latte/55">
                {report.shared_locations.slice(0, 6).map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
              <p className="mt-1.5 text-[11px] text-latte/40">
                Often one group with several trading names. Worth a look before they each get a
                letter.
              </p>
            </div>
          )}
          {report.unmapped_columns.length > 0 && (
            <p className="text-[11px] text-latte/40">
              Columns kept but not recognised: {report.unmapped_columns.join(', ')}
            </p>
          )}
          <p className="rounded-lg border border-caramel/20 bg-bean/30 px-3.5 py-2.5 text-[12px] leading-relaxed text-latte/65">
            {mode === 'automatic' ? (
              <>
                Sending has started. It works through the whole list on its own — about{' '}
                {Math.min(report.addresses, 50)} today, the rest on the days after — and keeps
                going when you close this page. You do not need to press anything again.
              </>
            ) : (
              <>
                Nothing is sent yet. Each email will be prepared for you to read first; press
                Start and the first draft appears.
              </>
            )}
          </p>

          <div className="flex gap-3">
            {mode === 'manual' && imported && (
              <Button
                loading={starting}
                onClick={async () => {
                  setStarting(true)
                  try {
                    await api.startCampaign(imported.id)
                    toast.success('Started. The first draft is ready to read.')
                    onDone()
                  } catch (err) {
                    toast.error(
                      err instanceof ApiError ? err.message : 'Could not start it.',
                    )
                  } finally {
                    setStarting(false)
                  }
                }}
              >
                Start now
              </Button>
            )}
            <Button variant={mode === 'manual' ? 'ghost' : 'primary'} onClick={onDone}>
              Done
            </Button>
          </div>
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
            <Field
              label="Sending"
              hint={
                mode === 'automatic'
                  ? 'Starts as soon as it is uploaded, and runs to the end of the list on its own.'
                  : 'Nothing goes out until you read and approve each one.'
              }
            >
              <Select
                value={mode}
                onChange={(e) => setMode(e.target.value)}
                options={[
                  { value: 'manual', label: 'Let me read each email first' },
                  { value: 'automatic', label: 'Just send them — 50 a day until the list is done' },
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
