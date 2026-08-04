import { useEffect, useState } from 'react'

import { Button, Field, Input, Select, Textarea } from './ui'
import { ApiError, api } from '../lib/api'
import { STATUS_ORDER, statusLabel } from '../lib/format'
import { useToast } from '../lib/toast'
import type { Contact, User } from '../lib/types'

const EMPTY = {
  company_name: '',
  country: '',
  contact_person: '',
  email: '',
  phone: '',
  whatsapp: '',
  trade_type: 'export',
  coffee_product: '',
  quantity_kg: '',
  roast_preference: '',
  bean_type: '',
  estimated_value_usd: '',
  status: 'new_lead',
  notes: '',
  next_follow_up: '',
  owner_id: '',
}

type FormState = typeof EMPTY

function toForm(contact: Contact): FormState {
  return {
    company_name: contact.company_name,
    country: contact.country,
    contact_person: contact.contact_person ?? '',
    email: contact.email ?? '',
    phone: contact.phone ?? '',
    whatsapp: contact.whatsapp ?? '',
    trade_type: contact.trade_type,
    coffee_product: contact.coffee_product ?? '',
    quantity_kg: contact.quantity_kg?.toString() ?? '',
    roast_preference: contact.roast_preference ?? '',
    bean_type: contact.bean_type ?? '',
    estimated_value_usd: contact.estimated_value_usd?.toString() ?? '',
    status: contact.status,
    notes: contact.notes ?? '',
    next_follow_up: contact.next_follow_up ?? '',
    owner_id: contact.owner_id?.toString() ?? '',
  }
}

export function ContactForm({
  contact,
  onSaved,
  onCancel,
}: {
  contact?: Contact
  onSaved: (c: Contact) => void
  onCancel: () => void
}) {
  const toast = useToast()
  const [form, setForm] = useState<FormState>(contact ? toForm(contact) : EMPTY)
  const [users, setUsers] = useState<User[]>([])
  const [busy, setBusy] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    api.listUsers().then(setUsers).catch(() => setUsers([]))
  }, [])

  const set = (key: keyof FormState) => (v: string) => setForm((f) => ({ ...f, [key]: v }))

  const validate = () => {
    const e: Record<string, string> = {}
    if (!form.company_name.trim()) e.company_name = 'Company name is required'
    if (!form.country.trim()) e.country = 'Country is required'
    if (form.email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email))
      e.email = 'Enter a valid email address'
    if (form.quantity_kg && Number(form.quantity_kg) < 0) e.quantity_kg = 'Cannot be negative'
    if (form.estimated_value_usd && Number(form.estimated_value_usd) < 0)
      e.estimated_value_usd = 'Cannot be negative'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault()
    if (!validate()) return
    setBusy(true)

    // Empty strings must become nulls, not "" — the API validates types.
    const payload: Record<string, unknown> = {
      company_name: form.company_name.trim(),
      country: form.country.trim(),
      contact_person: form.contact_person.trim() || null,
      email: form.email.trim() || null,
      phone: form.phone.trim() || null,
      whatsapp: form.whatsapp.trim() || null,
      trade_type: form.trade_type,
      coffee_product: form.coffee_product.trim() || null,
      quantity_kg: form.quantity_kg ? Number(form.quantity_kg) : null,
      roast_preference: form.roast_preference.trim() || null,
      bean_type: form.bean_type.trim() || null,
      estimated_value_usd: form.estimated_value_usd ? Number(form.estimated_value_usd) : null,
      status: form.status,
      notes: form.notes.trim() || null,
      next_follow_up: form.next_follow_up || null,
      owner_id: form.owner_id ? Number(form.owner_id) : null,
    }

    try {
      const saved = contact
        ? await api.updateContact(contact.id, payload)
        : await api.createContact(payload)
      toast.success(
        contact ? 'Account updated.' : `🌍 ${saved.company_name} added to the trade desk.`,
      )
      onSaved(saved)
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not save the account.')
    } finally {
      setBusy(false)
    }
  }

  return (
    // noValidate: the browser's native bubble for type="email" would suppress
    // our own inline messages, giving two inconsistent validation styles.
    <form onSubmit={submit} noValidate className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Company name *" error={errors.company_name}>
          <Input
            value={form.company_name}
            onChange={(e) => set('company_name')(e.target.value)}
            placeholder="ABC Coffee GmbH"
          />
        </Field>
        <Field label="Country *" error={errors.country}>
          <Input
            value={form.country}
            onChange={(e) => set('country')(e.target.value)}
            placeholder="Germany"
          />
        </Field>
        <Field label="Contact person">
          <Input
            value={form.contact_person}
            onChange={(e) => set('contact_person')(e.target.value)}
            placeholder="Lukas Weber"
          />
        </Field>
        <Field label="Trade type">
          <Select
            value={form.trade_type}
            onChange={(e) => set('trade_type')(e.target.value)}
            options={[
              { value: 'export', label: 'Export — we sell coffee' },
              { value: 'import', label: 'Import — we buy coffee' },
            ]}
          />
        </Field>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Email" error={errors.email}>
          <Input
            type="email"
            value={form.email}
            onChange={(e) => set('email')(e.target.value)}
            placeholder="buyer@company.com"
          />
        </Field>
        <Field label="Phone">
          <Input
            value={form.phone}
            onChange={(e) => set('phone')(e.target.value)}
            placeholder="+49 30 1234567"
          />
        </Field>
        <Field label="WhatsApp">
          <Input
            value={form.whatsapp}
            onChange={(e) => set('whatsapp')(e.target.value)}
            placeholder="+4915112345678"
          />
        </Field>
      </div>

      <div className="rounded-xl border border-caramel/15 bg-bean/25 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-gold/70">Coffee requirement</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Coffee product type">
            <Input
              value={form.coffee_product}
              onChange={(e) => set('coffee_product')(e.target.value)}
              placeholder="Arabica roasted beans"
            />
          </Field>
          <Field label="Quantity (kg)" error={errors.quantity_kg}>
            <Input
              type="number"
              min={0}
              step="any"
              value={form.quantity_kg}
              onChange={(e) => set('quantity_kg')(e.target.value)}
              placeholder="2000"
            />
          </Field>
          <Field label="Preferred roast">
            <Input
              value={form.roast_preference}
              onChange={(e) => set('roast_preference')(e.target.value)}
              placeholder="Medium roast"
            />
          </Field>
          <Field label="Bean type">
            <Input
              value={form.bean_type}
              onChange={(e) => set('bean_type')(e.target.value)}
              placeholder="Arabica"
            />
          </Field>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Status">
          <Select
            value={form.status}
            onChange={(e) => set('status')(e.target.value)}
            options={STATUS_ORDER.map((s) => ({ value: s, label: statusLabel(s) }))}
          />
        </Field>
        <Field label="Estimated value (USD)" error={errors.estimated_value_usd}>
          <Input
            type="number"
            min={0}
            step="any"
            value={form.estimated_value_usd}
            onChange={(e) => set('estimated_value_usd')(e.target.value)}
            placeholder="18500"
          />
        </Field>
        <Field label="Next follow-up">
          <Input
            type="date"
            value={form.next_follow_up}
            onChange={(e) => set('next_follow_up')(e.target.value)}
          />
        </Field>
      </div>

      <Field label="Assigned to">
        <Select
          value={form.owner_id}
          onChange={(e) => set('owner_id')(e.target.value)}
          options={[
            { value: '', label: 'Unassigned' },
            ...users.map((u) => ({ value: String(u.id), label: `${u.name} (${u.role})` })),
          ]}
        />
      </Field>

      <Field label="Notes">
        <Textarea
          rows={3}
          value={form.notes}
          onChange={(e) => set('notes')(e.target.value)}
          placeholder="Certifications required, shipping terms, packaging preferences…"
        />
      </Field>

      <div className="flex justify-end gap-3 border-t border-caramel/15 pt-4">
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" loading={busy}>
          {contact ? 'Save changes' : 'Add account'}
        </Button>
      </div>
    </form>
  )
}
