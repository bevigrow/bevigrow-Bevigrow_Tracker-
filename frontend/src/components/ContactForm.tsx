import { useEffect, useState } from 'react'

import { CountryInput, forgetCountries } from './CountryInput'
import { Button, Field, Input, Select, Textarea } from './ui'
import { ApiError, api } from '../lib/api'
import { STATUS_ORDER, statusLabel } from '../lib/format'
import { useToast } from '../lib/toast'
import type { Contact, User } from '../lib/types'

/**
 * Quote / RFQ entry.
 *
 * Nothing is mandatory. Marketplace RFQs routinely omit the email, phone,
 * port or even the country, and a form that refuses them means the enquiry
 * gets lost instead of recorded. The only fallback is a placeholder name so
 * the row can still be found later.
 */

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
  quantity_note: '',
  roast_preference: '',
  bean_type: '',
  origin_preference: '',
  hs_code: '',
  shipping_terms: '',
  destination_port: '',
  payment_terms: '',
  sourcing_from: '',
  rfq_source: '',
  rfq_reference: '',
  estimated_value_usd: '',
  status: 'new_lead',
  notes: '',
  next_follow_up: '',
  owner_id: '',
}

type FormState = typeof EMPTY

// Common incoterms and payment terms, but the inputs stay free text so an
// unusual one can always be typed in.
const SHIPPING_TERMS = ['CIF', 'FOB', 'CFR', 'EXW', 'FCA', 'DAP', 'DDP', 'CPT']
const PAYMENT_TERMS = ['T/T', 'L/C', 'T/T or L/C', 'D/P', 'D/A', 'Advance', '30% advance, 70% BL']

function toForm(contact: Contact): FormState {
  const str = (v: string | number | null | undefined) => (v === null || v === undefined ? '' : String(v))
  return {
    company_name: str(contact.company_name),
    country: str(contact.country),
    contact_person: str(contact.contact_person),
    email: str(contact.email),
    phone: str(contact.phone),
    whatsapp: str(contact.whatsapp),
    trade_type: contact.trade_type,
    coffee_product: str(contact.coffee_product),
    quantity_kg: str(contact.quantity_kg),
    quantity_note: str(contact.quantity_note),
    roast_preference: str(contact.roast_preference),
    bean_type: str(contact.bean_type),
    origin_preference: str(contact.origin_preference),
    hs_code: str(contact.hs_code),
    shipping_terms: str(contact.shipping_terms),
    destination_port: str(contact.destination_port),
    payment_terms: str(contact.payment_terms),
    sourcing_from: str(contact.sourcing_from),
    rfq_source: str(contact.rfq_source),
    rfq_reference: str(contact.rfq_reference),
    estimated_value_usd: str(contact.estimated_value_usd),
    status: contact.status,
    notes: str(contact.notes),
    next_follow_up: str(contact.next_follow_up),
    owner_id: str(contact.owner_id),
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

  useEffect(() => {
    api.listUsers().then(setUsers).catch(() => setUsers([]))
  }, [])

  const set = (key: keyof FormState) => (v: string) => setForm((f) => ({ ...f, [key]: v }))

  /** Blank strings become null; a non-numeric quantity is simply left out. */
  const text = (v: string) => (v.trim() ? v.trim() : null)
  const num = (v: string) => {
    const n = Number(v.replace(/[^0-9.]/g, ''))
    return v.trim() && Number.isFinite(n) && n !== 0 ? n : null
  }

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault()
    setBusy(true)

    const payload: Record<string, unknown> = {
      company_name: text(form.company_name),
      country: text(form.country),
      contact_person: text(form.contact_person),
      email: text(form.email),
      phone: text(form.phone),
      whatsapp: text(form.whatsapp),
      trade_type: form.trade_type,
      coffee_product: text(form.coffee_product),
      quantity_kg: num(form.quantity_kg),
      quantity_note: text(form.quantity_note),
      roast_preference: text(form.roast_preference),
      bean_type: text(form.bean_type),
      origin_preference: text(form.origin_preference),
      hs_code: text(form.hs_code),
      shipping_terms: text(form.shipping_terms),
      destination_port: text(form.destination_port),
      payment_terms: text(form.payment_terms),
      sourcing_from: text(form.sourcing_from),
      rfq_source: text(form.rfq_source),
      rfq_reference: text(form.rfq_reference),
      estimated_value_usd: num(form.estimated_value_usd),
      status: form.status,
      notes: text(form.notes),
      next_follow_up: form.next_follow_up || null,
      owner_id: form.owner_id ? Number(form.owner_id) : null,
    }

    try {
      const saved = contact
        ? await api.updateContact(contact.id, payload)
        : await api.createContact(payload)
      // A country typed here belongs in the next form's suggestions.
      forgetCountries()
      toast.success(contact ? 'Quote updated.' : `🌍 ${saved.company_name} saved.`)
      onSaved(saved)
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not save the quote.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-5">
      <p className="rounded-lg border border-caramel/20 bg-bean/30 px-3.5 py-2.5 text-[12px] text-latte/55">
        Every field is optional — save whatever the buyer actually gave you and fill the rest in
        later.
      </p>

      {/* ------------------------------------------------------- the buyer */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Company / buyer name" hint="Left blank, this is saved as “Untitled quote”">
          <Input
            value={form.company_name}
            onChange={(e) => set('company_name')(e.target.value)}
            placeholder="Saudi Coffee Shop"
          />
        </Field>
        <Field label="Country">
          <CountryInput
            value={form.country}
            onChange={set('country')}
            placeholder="Saudi Arabia"
          />
        </Field>
        <Field label="Contact person">
          <Input
            value={form.contact_person}
            onChange={(e) => set('contact_person')(e.target.value)}
            placeholder="Israr Ahmed"
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
        <Field label="Email" hint="Free text — “-” is fine">
          <Input
            value={form.email}
            onChange={(e) => set('email')(e.target.value)}
            placeholder="buyer@company.com"
          />
        </Field>
        <Field label="Phone">
          <Input value={form.phone} onChange={(e) => set('phone')(e.target.value)} placeholder="-" />
        </Field>
        <Field label="WhatsApp">
          <Input
            value={form.whatsapp}
            onChange={(e) => set('whatsapp')(e.target.value)}
            placeholder="-"
          />
        </Field>
      </div>

      {/* -------------------------------------------------- the requirement */}
      <div className="rounded-xl border border-caramel/15 bg-bean/25 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-gold/70">
          Coffee requirement
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Product">
            <Input
              value={form.coffee_product}
              onChange={(e) => set('coffee_product')(e.target.value)}
              placeholder="Green coffee beans / roasted / powder"
            />
          </Field>
          <Field label="Variety / bean type">
            <Input
              value={form.bean_type}
              onChange={(e) => set('bean_type')(e.target.value)}
              placeholder="Arabica and Robusta"
            />
          </Field>
          <Field
            label="Quantity as written"
            hint="Copy the buyer's wording"
          >
            <Input
              value={form.quantity_note}
              onChange={(e) => set('quantity_note')(e.target.value)}
              placeholder="600 kg each item · 1 twenty-foot container"
            />
          </Field>
          <Field label="Quantity in kg" hint="Numbers only — used for reporting">
            <Input
              inputMode="decimal"
              value={form.quantity_kg}
              onChange={(e) => set('quantity_kg')(e.target.value)}
              placeholder="600"
            />
          </Field>
          <Field label="Roast preference">
            <Input
              value={form.roast_preference}
              onChange={(e) => set('roast_preference')(e.target.value)}
              placeholder="Roasted / green / medium"
            />
          </Field>
          <Field label="Origin preference">
            <Input
              value={form.origin_preference}
              onChange={(e) => set('origin_preference')(e.target.value)}
              placeholder="Brazil, Colombia and Ethiopia"
            />
          </Field>
        </div>
      </div>

      {/* ------------------------------------------------------ trade terms */}
      <div className="rounded-xl border border-caramel/15 bg-bean/25 p-4">
        <p className="mb-3 text-[11px] uppercase tracking-wider text-gold/70">Trade terms</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Shipping terms">
            <Input
              list="shipping-terms"
              value={form.shipping_terms}
              onChange={(e) => set('shipping_terms')(e.target.value)}
              placeholder="CIF"
            />
            <datalist id="shipping-terms">
              {SHIPPING_TERMS.map((t) => (
                <option key={t} value={t} />
              ))}
            </datalist>
          </Field>
          <Field label="Destination port">
            <Input
              value={form.destination_port}
              onChange={(e) => set('destination_port')(e.target.value)}
              placeholder="Jeddah, Saudi Arabia"
            />
          </Field>
          <Field label="Payment terms">
            <Input
              list="payment-terms"
              value={form.payment_terms}
              onChange={(e) => set('payment_terms')(e.target.value)}
              placeholder="T/T or L/C"
            />
            <datalist id="payment-terms">
              {PAYMENT_TERMS.map((t) => (
                <option key={t} value={t} />
              ))}
            </datalist>
          </Field>
          <Field label="HS code">
            <Input
              value={form.hs_code}
              onChange={(e) => set('hs_code')(e.target.value)}
              placeholder="090111, 090121"
            />
          </Field>
          <Field label="Sourcing from" hint="Where the buyer wants suppliers">
            <Input
              value={form.sourcing_from}
              onChange={(e) => set('sourcing_from')(e.target.value)}
              placeholder="Worldwide · India, Africa"
            />
          </Field>
          <Field label="Estimated value (USD)">
            <Input
              inputMode="decimal"
              value={form.estimated_value_usd}
              onChange={(e) => set('estimated_value_usd')(e.target.value)}
              placeholder="18500"
            />
          </Field>
        </div>
      </div>

      {/* --------------------------------------------------------- tracking */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Where this RFQ came from">
          <Input
            value={form.rfq_source}
            onChange={(e) => set('rfq_source')(e.target.value)}
            placeholder="Alibaba · TradeIndia · direct email"
          />
        </Field>
        <Field label="RFQ reference">
          <Input
            value={form.rfq_reference}
            onChange={(e) => set('rfq_reference')(e.target.value)}
            placeholder="RFQ-2026-0142"
          />
        </Field>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Status">
          <Select
            value={form.status}
            onChange={(e) => set('status')(e.target.value)}
            options={STATUS_ORDER.map((s) => ({ value: s, label: statusLabel(s) }))}
          />
        </Field>
        <Field label="Next follow-up">
          <Input
            type="date"
            value={form.next_follow_up}
            onChange={(e) => set('next_follow_up')(e.target.value)}
          />
        </Field>
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
      </div>

      <Field label="Notes" hint="Paste the whole RFQ text here if it's easier">
        <Textarea
          rows={4}
          value={form.notes}
          onChange={(e) => set('notes')(e.target.value)}
          placeholder="Buyer is interested to receive quotations for the following RFQ…"
        />
      </Field>

      <div className="flex justify-end gap-3 border-t border-caramel/15 pt-4">
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" loading={busy}>
          {contact ? 'Save changes' : 'Save quote'}
        </Button>
      </div>
    </form>
  )
}
