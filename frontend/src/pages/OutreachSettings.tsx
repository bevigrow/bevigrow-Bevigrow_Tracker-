/**
 * The mailbox campaigns send from, and the email they send.
 *
 * Connecting is deliberately its own screen with its own Test button. An app
 * password that was mistyped fails exactly like one that was revoked, and
 * finding that out on company one of two hundred is a bad way to learn it.
 */
import {
  CheckCircle2,
  Inbox,
  KeyRound,
  Mail,
  Plus,
  Play,
  RefreshCw,
  Square,
  ShieldCheck,
  TriangleAlert,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { Button, Card, Field, Input, Select, Skeleton, Textarea } from '../components/ui'
import { ApiError, api } from '../lib/api'
import { formatDateTime } from '../lib/format'
import { useToast } from '../lib/toast'
import type { EmailAccount, EmailTemplate } from '../lib/types'

export function OutreachSettings() {
  const toast = useToast()
  const [account, setAccount] = useState<EmailAccount | null>(null)
  const [templates, setTemplates] = useState<EmailTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [testing, setTesting] = useState(false)

  const [form, setForm] = useState({
    from_email: '',
    from_name: '',
    password: '',
    provider: 'smtp',
    api_key: '',
    reply_to: '',
  })

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [acct, tpls] = await Promise.all([
        api.emailAccount().catch(() => null),
        api.listTemplates().catch(() => []),
      ])
      setAccount(acct)
      setTemplates(tpls)
      if (acct)
        setForm((f) => ({
          ...f,
          from_email: acct.from_email,
          from_name: acct.from_name,
          provider: acct.provider ?? 'smtp',
          reply_to: acct.reply_to ?? '',
        }))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      const saved = await api.saveEmailAccount({
        from_email: form.from_email.trim(),
        from_name: form.from_name.trim(),
        provider: form.provider,
        smtp_user: form.from_email.trim(),
        reply_to: form.reply_to.trim() || null,
        // Omitted when blank, so saving the display name does not wipe a
        // secret that is already stored and working.
        ...(form.password.trim() ? { password: form.password.trim() } : {}),
        ...(form.api_key.trim() ? { api_key: form.api_key.trim() } : {}),
      })
      setAccount(saved)
      setForm((f) => ({ ...f, password: '', api_key: '' }))
      toast.success('Mailbox saved.')
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not save the mailbox.')
    } finally {
      setBusy(false)
    }
  }

  const test = async () => {
    setTesting(true)
    try {
      setAccount(await api.verifyEmailAccount())
      toast.success('Signed in to the mailbox successfully.')
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not sign in.')
      void load()
    } finally {
      setTesting(false)
    }
  }

  if (loading) return <Skeleton className="h-96" />

  const isSmtp = form.provider === 'smtp'
  const connected = isSmtp ? account?.has_password : account?.has_api_key
  const verified = Boolean(account?.last_verified_at)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl text-latte">Outreach Settings</h1>
        <p className="mt-1 text-sm text-latte/50">
          The mailbox campaigns send from, and the email they send.
        </p>
      </div>

      {/* ------------------------------------------------------- the mailbox */}
      <Card>
        <div className="mb-4 flex items-start justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <Mail size={18} className="text-gold" />
            <div>
              <h2 className="font-display text-lg text-latte">Sending mailbox</h2>
              <p className="text-[11px] text-latte/45">
                {isSmtp
                  ? 'Gmail over SMTP with an App Password.'
                  : 'Sent over HTTPS, with replies pointed at your Gmail.'}
              </p>
            </div>
          </div>
          {connected && (
            <span
              className={`chip shrink-0 ${
                verified
                  ? 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300'
                  : 'border-caramel/30 bg-bean/40 text-latte/60'
              }`}
            >
              {verified ? <CheckCircle2 size={12} /> : <KeyRound size={12} />}
              {verified ? 'Verified' : 'Not tested'}
            </span>
          )}
        </div>

        <form onSubmit={save} className="space-y-4">
          <Field
            label="How the mail leaves"
            hint={
              isSmtp
                ? 'Sends from your own mailbox. Needs a host that allows outbound port 587 - free Render instances do not.'
                : 'Sends over HTTPS, which no host blocks. Verify your sending domain with the provider first.'
            }
          >
            <Select
              value={form.provider}
              onChange={(e) => setForm({ ...form, provider: e.target.value })}
              options={[
                { value: 'smtp', label: 'Gmail directly (SMTP + App Password)' },
                { value: 'resend', label: 'Resend (HTTPS - works on free hosting)' },
                { value: 'brevo', label: 'Brevo (HTTPS - works on free hosting)' },
              ]}
            />
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label={isSmtp ? 'Gmail address' : 'Send from'}
              hint={
                isSmtp
                  ? 'Mail is sent from here, and replies arrive here'
                  : 'An address at a domain you have verified with the provider'
              }
            >
              <Input
                type="email"
                value={form.from_email}
                onChange={(e) => setForm({ ...form, from_email: e.target.value })}
                placeholder="bevigrow@gmail.com"
              />
            </Field>
            <Field label="Sender name" hint="What the recipient sees in the From line">
              <Input
                value={form.from_name}
                onChange={(e) => setForm({ ...form, from_name: e.target.value })}
                placeholder="BeviGrow Coffee"
              />
            </Field>
          </div>

          {isSmtp ? (
            <Field
              label="App Password"
              hint={
                connected
                  ? 'A password is stored. Leave blank to keep it, or paste a new one to replace it.'
                  : 'Sixteen characters from Google, not your account password.'
              }
            >
              <Input
                type="password"
                autoComplete="new-password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder={connected ? 'stored' : 'abcd efgh ijkl mnop'}
              />
            </Field>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                label="API key"
                hint={
                  connected
                    ? 'A key is stored. Leave blank to keep it.'
                    : form.provider === 'resend'
                      ? 'resend.com then API Keys'
                      : 'Brevo then SMTP & API then API Keys'
                }
              >
                <Input
                  type="password"
                  autoComplete="new-password"
                  value={form.api_key}
                  onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                  placeholder={connected ? 'stored' : 're_xxxxxxxx'}
                />
              </Field>
              <Field label="Replies go to" hint="Your Gmail, so answers land where you read them">
                <Input
                  type="email"
                  value={form.reply_to}
                  onChange={(e) => setForm({ ...form, reply_to: e.target.value })}
                  placeholder="bevigrow@gmail.com"
                />
              </Field>
            </div>
          )}

          {account?.last_error && (
            <p className="flex items-start gap-2 rounded-lg border border-red-500/25 bg-red-500/10 px-3.5 py-2.5 text-[12px] text-red-200">
              <TriangleAlert size={14} className="mt-0.5 shrink-0" />
              {account.last_error}
            </p>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" loading={busy}>
              {connected ? 'Update mailbox' : 'Connect mailbox'}
            </Button>
            {connected && (
              <Button
                type="button"
                variant="ghost"
                onClick={test}
                loading={testing}
                icon={<ShieldCheck size={15} />}
              >
                Test connection
              </Button>
            )}
            {verified && account?.last_verified_at && (
              <span className="text-[11px] text-latte/40">
                Last verified {formatDateTime(account.last_verified_at)}
              </span>
            )}
          </div>
        </form>

        <details className="mt-5 rounded-lg border border-caramel/20 bg-bean/30 px-3.5 py-3">
          <summary className="cursor-pointer text-[12px] font-medium text-latte/70">
            How to get an App Password
          </summary>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-[12px] leading-relaxed text-latte/55">
            <li>Turn on 2-Step Verification in your Google account.</li>
            <li>
              Go to <span className="text-gold">myaccount.google.com</span> → Security → App
              passwords.
            </li>
            <li>Create one for “Mail”, and paste the sixteen characters above.</li>
            <li>Press Test connection. Nothing is sent — it signs in and hangs up.</li>
          </ol>
          <p className="mt-2 text-[11px] text-latte/40">
            The password is encrypted before it is stored, and is never shown again — not in this
            page, not in the API, not in the logs.
          </p>
        </details>
      </Card>

      {/* --------------------------------------------------- reading replies */}
      <ReplyTracking account={account} onSaved={load} />

      {/* ------------------------------------------------------- the template */}
      <TemplateEditor templates={templates} onSaved={load} />
    </div>
  )
}

/* ------------------------------------------------------------ reply tracking */

/** Connecting the mailbox replies arrive in.
 *
 * Sending and reading are two different connections to two different places:
 * campaigns leave over HTTPS because the host blocks the SMTP ports, and
 * replies are read over IMAP, which is reachable. So this is its own panel
 * with its own password, rather than a checkbox on the sending one.
 */
function ReplyTracking({
  account,
  onSaved,
}: {
  account: EmailAccount | null
  onSaved: () => Promise<void> | void
}) {
  const toast = useToast()
  const [user, setUser] = useState(account?.imap_user || account?.reply_to || '')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [checking, setChecking] = useState(false)
  // Reading the inbox on a repeat, for as long as this page is open and the
  // switch is on. Deliberately not a server-side timer: a background task
  // that reads mail every minute is a database query every minute whether or
  // not anyone is there, which is what exhausted the plan. Driven from here,
  // it cannot outlive the tab it was started in.
  const [reading, setReading] = useState(false)
  const [readCount, setReadCount] = useState(0)

  if (!account)
    return (
      <Card>
        <div className="flex items-center gap-2.5">
          <Inbox size={18} className="text-latte/30" />
          <p className="text-sm text-latte/50">
            Save the sending mailbox above first, then connect the inbox replies arrive in.
          </p>
        </div>
      </Card>
    )

  const connected = Boolean(account.has_imap_password && account.imap_user)
  const enabled = account.reply_check_enabled

  // The PUT replaces the whole record, so the sending half has to travel with
  // it — otherwise connecting the inbox would quietly blank the From address.
  const put = async (extra: Record<string, unknown>) => {
    setBusy(true)
    try {
      await api.saveEmailAccount({
        from_email: account.from_email,
        from_name: account.from_name,
        provider: account.provider,
        smtp_user: account.smtp_user,
        reply_to: account.reply_to,
        daily_limit: account.daily_limit,
        imap_host: account.imap_host || 'imap.gmail.com',
        imap_port: account.imap_port || 993,
        reply_check_enabled: enabled,
        ...extra,
      })
      setPassword('')
      await onSaved()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not save.')
    } finally {
      setBusy(false)
    }
  }

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!user.trim()) {
      toast.error('Which mailbox should be read?')
      return
    }
    if (!connected && !password.trim()) {
      toast.error('An App Password is needed the first time.')
      return
    }
    await put({
      imap_user: user.trim(),
      reply_check_enabled: true,
      ...(password.trim() ? { imap_password: password.trim() } : {}),
    })
    toast.success('Inbox connected. Replies will be picked up automatically.')
  }

  useEffect(() => {
    if (!reading) return
    let cancelled = false

    const once = async () => {
      try {
        const r = await api.checkReplies()
        if (cancelled) return
        setReadCount((n) => n + 1)
        if (r.error) {
          toast.error(r.error)
          setReading(false)
        } else if (r.stored) {
          toast.success(
            `${r.stored} new: ${r.matched} matched to a company, ${r.unmatched} need a look.`,
          )
          await onSaved()
        }
      } catch (err) {
        if (cancelled) return
        toast.error(err instanceof ApiError ? err.message : 'Could not read the mailbox.')
        setReading(false)
      }
    }

    void once()
    const timer = window.setInterval(() => void once(), 60_000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reading])

  const checkNow = async () => {
    setChecking(true)
    try {
      const r = await api.checkReplies()
      if (r.error) toast.error(r.error)
      else if (r.stored === 0) toast.success(`Read ${r.checked} messages — nothing new.`)
      else
        toast.success(
          `${r.stored} new: ${r.matched} matched to a company, ${r.unmatched} need a look.`,
        )
      await onSaved()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not read the mailbox.')
    } finally {
      setChecking(false)
    }
  }

  return (
    <Card>
      <div className="mb-4 flex items-start justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <Inbox size={18} className="text-gold" />
          <div>
            <h2 className="font-display text-lg text-latte">Reply tracking</h2>
            <p className="text-[11px] text-latte/45">
              Press Check now and every reply updates its own record.
            </p>
          </div>
        </div>
        {connected && (
          <span
            className={`chip shrink-0 ${
              account.last_reply_error
                ? 'border-red-400/40 bg-red-400/10 text-red-300'
                : 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300'
            }`}
          >
            <CheckCircle2 size={12} />
            {account.last_reply_error ? 'Needs attention' : enabled ? 'Connected' : 'Paused'}
          </span>
        )}
      </div>

      <form onSubmit={save} className="grid gap-4 sm:grid-cols-2">
        <Field label="Mailbox to read">
          <Input
            value={user}
            onChange={(e) => setUser(e.target.value)}
            placeholder="bevigrow@gmail.com"
            autoComplete="off"
          />
        </Field>
        <Field label={connected ? 'App Password (already stored)' : 'App Password'}>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={connected ? 'Leave blank to keep the saved one' : 'sixteen characters'}
            autoComplete="new-password"
          />
        </Field>

        <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
          <Button type="submit" disabled={busy}>
            {busy ? 'Saving…' : connected ? 'Reconnect' : 'Connect inbox'}
          </Button>
          {connected && (
            <>
              <Button type="button" variant="ghost" onClick={checkNow} disabled={checking || reading}>
                <RefreshCw size={14} className={checking ? 'animate-spin' : undefined} />
                {checking ? 'Reading…' : 'Check now'}
              </Button>
              {/* Keep reading, once a minute, until told to stop. Closing the
                  page stops it too — nothing carries on server-side. */}
              <Button
                type="button"
                variant={reading ? 'primary' : 'ghost'}
                onClick={() => {
                  setReadCount(0)
                  setReading((v) => !v)
                }}
              >
                {reading ? (
                  <>
                    <Square size={13} /> Stop reading
                  </>
                ) : (
                  <>
                    <Play size={13} /> Keep reading
                  </>
                )}
              </Button>
              {reading && (
                <span className="text-[11px] text-emerald-300/80">
                  Watching the inbox — checked {readCount} time{readCount === 1 ? '' : 's'}. Stays
                  on only while this page is open.
                </span>
              )}
              <Button
                type="button"
                variant="ghost"
                onClick={async () => {
                  await put({ imap_user: account.imap_user, reply_check_enabled: !enabled })
                  toast.success(enabled ? 'Automatic checking paused.' : 'Checking again.')
                }}
                disabled={busy}
              >
                {enabled ? 'Turn off reply reading' : 'Turn reply reading on'}
              </Button>
            </>
          )}
          {account.last_reply_check_at && (
            <span className="text-[11px] text-latte/40">
              Last read {formatDateTime(account.last_reply_check_at)}
            </span>
          )}
        </div>
      </form>

      {account.last_reply_error && (
        <p className="mt-4 flex items-start gap-2 rounded-lg border border-red-400/30 bg-red-400/5 px-3 py-2.5 text-[12px] text-red-200/80">
          <TriangleAlert size={14} className="mt-0.5 shrink-0" />
          {account.last_reply_error}
        </p>
      )}

      <p className="mt-4 flex items-start gap-2 rounded-lg border border-caramel/20 bg-bean/30 px-3 py-2.5 text-[12px] leading-relaxed text-latte/55">
        <ShieldCheck size={14} className="mt-0.5 shrink-0 text-gold/70" />
        Replies are read when you press <span className="text-latte/75">Check now</span> —
        nothing is read on a timer, because reading on a timer keeps the database awake
        and a free plan does not survive that. A matched reply marks the company{' '}
        <span className="text-latte/75">Replied</span>, saves what they wrote, records how long they
        took and stops any follow-up to them. Nothing is ever written back — answering is done in
        Gmail, by you.
      </p>
    </Card>
  )
}

/* ------------------------------------------------------------------ template */

const EMPTY_TEMPLATE = { name: '', subject: '', body: '', instructions: '' }

function TemplateEditor({
  templates,
  onSaved,
}: {
  templates: EmailTemplate[]
  onSaved: () => void
}) {
  const toast = useToast()
  const [editing, setEditing] = useState<EmailTemplate | null>(templates[0] ?? null)
  const [form, setForm] = useState(
    templates[0]
      ? {
          name: templates[0].name,
          subject: templates[0].subject,
          body: templates[0].body,
          instructions: templates[0].instructions ?? '',
        }
      : EMPTY_TEMPLATE,
  )
  const [busy, setBusy] = useState(false)

  const pick = (t: EmailTemplate | null) => {
    setEditing(t)
    setForm(
      t
        ? { name: t.name, subject: t.subject, body: t.body, instructions: t.instructions ?? '' }
        : EMPTY_TEMPLATE,
    )
  }

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      const body = {
        name: form.name.trim(),
        subject: form.subject.trim(),
        body: form.body,
        instructions: form.instructions.trim() || null,
      }
      const saved = editing
        ? await api.updateTemplate(editing.id, body)
        : await api.createTemplate(body)
      setEditing(saved)
      toast.success('Template saved.')
      onSaved()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not save the template.')
    } finally {
      setBusy(false)
    }
  }

  // Shown live, so it is obvious which words will be replaced before a
  // campaign puts them in front of a buyer.
  const found = Array.from(
    new Set(
      `${form.subject}\n${form.body}`.match(/#[A-Z][A-Z0-9_]{2,}|\{\{[^}]+\}\}/g) ?? [],
    ),
  )

  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-lg text-latte">Email template</h2>
          <p className="text-[11px] text-latte/45">
            Your words, sent as written. Only the placeholders are filled in.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {templates.map((t) => (
            <button
              key={t.id}
              onClick={() => pick(t)}
              className={`chip ${
                editing?.id === t.id
                  ? 'border-gold/50 bg-gold/15 text-gold'
                  : 'border-caramel/25 bg-bean/40 text-latte/60'
              }`}
            >
              {t.name}
            </button>
          ))}
          <button
            onClick={() => pick(null)}
            className="chip border-caramel/25 bg-bean/40 text-latte/60 hover:border-gold/40"
          >
            <Plus size={11} /> New
          </button>
        </div>
      </div>

      <form onSubmit={save} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Template name" hint="For you, never sent">
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Japan importers"
            />
          </Field>
          <Field label="Subject line">
            <Input
              value={form.subject}
              onChange={(e) => setForm({ ...form, subject: e.target.value })}
              placeholder="Green coffee from BeviGrow — #COMPANY"
            />
          </Field>
        </div>

        <Field
          label="Body"
          hint="Write it as you would send it. #COMPANY, #COMPANY_TEAM, #CONTACT, #COUNTRY and #CITY are filled per company."
        >
          <Textarea
            rows={14}
            value={form.body}
            onChange={(e) => setForm({ ...form, body: e.target.value })}
            placeholder={
              'Dear #COMPANY_TEAM,\n\n' +
              'I am writing from BeviGrow, a coffee exporter in Kerala, India.\n\n' +
              '…\n\n' +
              'Kind regards,\nBeviGrow Coffee\n[your address]\n' +
              'Reply with “no thanks” and we will not write again.'
            }
            className="font-mono text-[12.5px] leading-relaxed"
          />
        </Field>

        {found.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-latte/45">
            Placeholders found:
            {found.map((p) => (
              <span key={p} className="chip border-gold/30 bg-gold/10 text-gold">
                {p}
              </span>
            ))}
          </div>
        )}

        <p className="rounded-lg border border-caramel/20 bg-bean/30 px-3.5 py-2.5 text-[11.5px] leading-relaxed text-latte/55">
          Include your company name, a postal address and one line telling people how to opt out.
          Germany, Finland and Norway require it for business email, and it is also what keeps a
          Gmail account from being flagged. A row that cannot fill a placeholder is held back
          rather than sent — nobody receives “Dear #COMPANY_TEAM”.
        </p>

        <Button type="submit" loading={busy}>
          {editing ? 'Save template' : 'Create template'}
        </Button>
      </form>
    </Card>
  )
}
