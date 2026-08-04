import { Sparkles, Wand2 } from 'lucide-react'
import { useState } from 'react'

import { Button, Field, Input, Select, Textarea } from './ui'
import { ApiError, api } from '../lib/api'
import { CHANNEL_META, STATUS_ORDER, statusLabel, todayISO } from '../lib/format'
import { useToast } from '../lib/toast'
import type { Activity, Channel, Contact } from '../lib/types'

export function ActivityForm({
  contact,
  onSaved,
  onCancel,
}: {
  contact: Contact
  onSaved: (a: Activity) => void
  onCancel: () => void
}) {
  const toast = useToast()
  const [channel, setChannel] = useState<Channel>('call')
  const [discussion, setDiscussion] = useState('')
  const [reply, setReply] = useState('')
  const [followUp, setFollowUp] = useState('')
  const [statusAfter, setStatusAfter] = useState('')
  const [occurredAt, setOccurredAt] = useState(() => {
    // datetime-local wants local time without a timezone suffix.
    const d = new Date()
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
    return d.toISOString().slice(0, 16)
  })
  const [generate, setGenerate] = useState(true)
  const [preview, setPreview] = useState('')
  const [previewing, setPreviewing] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const previewSummary = async () => {
    if (discussion.trim().length < 5) {
      setError('Write a few words about the discussion first.')
      return
    }
    setError('')
    setPreviewing(true)
    try {
      const notes = reply.trim() ? `${discussion}\nCustomer reply: ${reply}` : discussion
      const res = await api.summarize(notes, contact.company_name, contact.country)
      setPreview(res.summary)
      if (!res.ai_enabled) {
        toast.info('Claude Haiku is not configured — showing the built-in summary.')
      }
    } catch {
      toast.error('Could not generate a summary.')
    } finally {
      setPreviewing(false)
    }
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (discussion.trim().length < 3) {
      setError('Please describe what was discussed.')
      return
    }
    setError('')
    setBusy(true)
    try {
      const saved = await api.createActivity({
        contact_id: contact.id,
        channel,
        discussion: discussion.trim(),
        customer_reply: reply.trim() || null,
        next_follow_up: followUp || null,
        status_after: statusAfter || null,
        occurred_at: new Date(occurredAt).toISOString(),
        generate_summary: generate,
      })
      toast.success('☕ Interaction logged and summarised.')
      onSaved(saved)
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not log the interaction.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Communication mode">
          <Select
            value={channel}
            onChange={(e) => setChannel(e.target.value as Channel)}
            options={(Object.keys(CHANNEL_META) as Channel[]).map((c) => ({
              value: c,
              label: `${CHANNEL_META[c].icon}  ${CHANNEL_META[c].label}`,
            }))}
          />
        </Field>
        <Field label="Date &amp; time">
          <Input
            type="datetime-local"
            value={occurredAt}
            onChange={(e) => setOccurredAt(e.target.value)}
          />
        </Field>
      </div>

      <Field label="What was discussed *" error={error}>
        <Textarea
          rows={4}
          value={discussion}
          onChange={(e) => setDiscussion(e.target.value)}
          placeholder="Called ABC Coffee Germany. They asked for 2 tons Arabica roasted beans and requested a quotation by tomorrow."
        />
      </Field>

      <Field label="Customer reply">
        <Textarea
          rows={2}
          value={reply}
          onChange={(e) => setReply(e.target.value)}
          placeholder="Confirmed budget approved; wants FOB pricing."
        />
      </Field>

      {/* AI summary preview */}
      <div className="rounded-xl border border-gold/25 bg-gold/[0.06] p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Sparkles size={15} className="text-gold" />
            <span className="text-sm font-medium text-latte/85">AI summary</span>
            <span className="text-[10px] uppercase tracking-wider text-gold/60">Claude Haiku</span>
          </div>
          <Button
            type="button"
            variant="ghost"
            onClick={previewSummary}
            loading={previewing}
            icon={<Wand2 size={13} />}
            className="px-3 py-1.5 text-xs"
          >
            Preview
          </Button>
        </div>

        {preview && (
          <p className="mt-3 rounded-lg bg-bean/40 p-3 text-sm italic leading-relaxed text-latte/80">
            {preview}
          </p>
        )}

        <label className="mt-3 flex cursor-pointer items-center gap-2 text-xs text-latte/55">
          <input
            type="checkbox"
            checked={generate}
            onChange={(e) => setGenerate(e.target.checked)}
            className="h-3.5 w-3.5 accent-[#D9A05B]"
          />
          Generate and store a professional summary with this entry
        </label>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Next follow-up date" hint="Creates a reminder automatically">
          <Input
            type="date"
            min={todayISO()}
            value={followUp}
            onChange={(e) => setFollowUp(e.target.value)}
          />
        </Field>
        <Field label="Move status to" hint="Optional — updates the account stage">
          <Select
            value={statusAfter}
            onChange={(e) => setStatusAfter(e.target.value)}
            options={[
              { value: '', label: 'Leave unchanged' },
              ...STATUS_ORDER.map((s) => ({ value: s, label: statusLabel(s) })),
            ]}
          />
        </Field>
      </div>

      <div className="flex justify-end gap-3 border-t border-caramel/15 pt-4">
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" loading={busy}>
          Log interaction
        </Button>
      </div>
    </form>
  )
}
