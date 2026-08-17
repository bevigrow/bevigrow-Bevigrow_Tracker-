/**
 * Country field with suggestions from the countries already in the app.
 *
 * Country is free text on purpose — an RFQ says "Dubai" where the shipping
 * document says "United Arab Emirates", and a fixed dropdown would lose the
 * enquiry rather than record it. The price of free text is spelling drift:
 * "Japan", "japan" and "Japan " count as three countries in every breakdown,
 * and by the time anyone notices, the numbers have been wrong for a month.
 *
 * So this keeps the field free, and leans on the entries already in use:
 *   · a datalist completes what has been typed before,
 *   · leaving the field adopts the existing spelling of the same name,
 *   · a near miss ("Norwey", "United State") offers the country it resembles,
 *     to accept or ignore.
 */
import { useEffect, useMemo, useState } from 'react'

import { Input } from './ui'
import { api } from '../lib/api'
import type { CountryOption } from '../lib/types'

/* --------------------------------------------------------------- the list */

// Cached across mounts: every quote and outreach form would otherwise fetch
// the same list each time a modal opens.
let pending: Promise<CountryOption[]> | null = null

export function knownCountries(): Promise<CountryOption[]> {
  pending ??= api.countryOptions().catch(() => [] as CountryOption[])
  return pending
}

/** Call after saving a record — a country typed just now belongs in the list. */
export function forgetCountries(): void {
  pending = null
}

/* ------------------------------------------------------------- comparison */

const canon = (raw: string) => raw.trim().replace(/\s+/g, ' ').toLowerCase()

/** Dice coefficient over letter bigrams: 1 is identical, 0 shares nothing. */
function similarity(a: string, b: string): number {
  if (a === b) return 1
  if (a.length < 2 || b.length < 2) return 0
  const pairs = (s: string) => {
    const out: string[] = []
    for (let i = 0; i < s.length - 1; i++) out.push(s.slice(i, i + 2))
    return out
  }
  const left = pairs(a)
  const right = pairs(b)
  let hits = 0
  const pool = [...right]
  for (const p of left) {
    const at = pool.indexOf(p)
    if (at >= 0) {
      pool.splice(at, 1)
      hits++
    }
  }
  return (2 * hits) / (left.length + right.length)
}

/**
 * The country this text most likely meant, or null if it is already exact,
 * too short to judge, or nothing close enough to be worth suggesting.
 */
export function nearestCountry(typed: string, known: CountryOption[]): string | null {
  const key = canon(typed)
  if (key.length < 3) return null
  if (known.some((c) => canon(c.name) === key)) return null

  let best: { name: string; score: number } | null = null
  for (const c of known) {
    const other = canon(c.name)
    // A prefix counts as a strong match: "united" should offer "United States"
    // before any bigram score gets a say.
    const score = other.startsWith(key) || key.startsWith(other) ? 0.95 : similarity(key, other)
    if (!best || score > best.score) best = { name: c.name, score }
  }
  return best && best.score >= 0.68 ? best.name : null
}

/* ----------------------------------------------------------------- field */

export function CountryInput({
  value,
  onChange,
  placeholder = 'Norway',
  id = 'known-countries',
}: {
  value: string
  onChange: (next: string) => void
  placeholder?: string
  id?: string
}) {
  const [known, setKnown] = useState<CountryOption[]>([])

  useEffect(() => {
    let live = true
    void knownCountries().then((list) => live && setKnown(list))
    return () => {
      live = false
    }
  }, [])

  const suggestion = useMemo(() => nearestCountry(value, known), [value, known])

  /** On the way out, settle on the spelling already in use for this country. */
  const settle = () => {
    const tidy = value.trim().replace(/\s+/g, ' ')
    const match = known.find((c) => canon(c.name) === canon(tidy))
    const next = match ? match.name : tidy
    if (next !== value) onChange(next)
  }

  return (
    <>
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={settle}
        placeholder={placeholder}
        list={id}
        autoComplete="off"
      />
      <datalist id={id}>
        {known.map((c) => (
          <option key={c.name} value={c.name} />
        ))}
      </datalist>
      {suggestion && (
        <p className="mt-1 text-[11px] text-latte/45">
          Did you mean{' '}
          <button
            type="button"
            onClick={() => onChange(suggestion)}
            className="font-medium text-gold hover:underline"
          >
            {suggestion}
          </button>
          ? Same spelling keeps the country on one line in your reports.
        </p>
      )}
    </>
  )
}
