import { Loader2, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { ButtonHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react'
import type { InputHTMLAttributes, TextareaHTMLAttributes } from 'react'

import { STATUS_META } from '../../lib/format'
import type { DealStatus } from '../../lib/types'

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(' ')
}

/* ------------------------------------------------------------------ card */

interface CardProps {
  children: ReactNode
  className?: string
  /** Emit a coffee ripple from the cursor on hover. */
  ripple?: boolean
  onClick?: () => void
}

export function Card({ children, className, ripple = false, onClick }: CardProps) {
  const ref = useRef<HTMLDivElement>(null)

  const handleEnter = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!ripple || !ref.current) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const rect = ref.current.getBoundingClientRect()
    const span = document.createElement('span')
    span.className = 'ripple'
    span.style.left = `${e.clientX - rect.left}px`
    span.style.top = `${e.clientY - rect.top}px`
    ref.current.appendChild(span)
    window.setTimeout(() => span.remove(), 720)
  }

  return (
    <div
      ref={ref}
      onMouseEnter={handleEnter}
      onClick={onClick}
      className={cx(
        'card p-5',
        ripple && 'ripple-host card-hover',
        onClick && 'cursor-pointer',
        className,
      )}
    >
      <div className="relative z-10">{children}</div>
    </div>
  )
}

/* ---------------------------------------------------------------- button */

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'ghost' | 'danger'
  loading?: boolean
  icon?: ReactNode
}

export function Button({
  variant = 'primary',
  loading = false,
  icon,
  children,
  className,
  disabled,
  ...rest
}: ButtonProps) {
  const cls =
    variant === 'primary' ? 'btn-primary' : variant === 'danger' ? 'btn-danger' : 'btn-ghost'
  return (
    <button {...rest} disabled={disabled || loading} className={cx(cls, className)}>
      {loading ? <Loader2 size={15} className="animate-spin" /> : icon}
      {children}
    </button>
  )
}

/* ----------------------------------------------------------------- inputs */

interface FieldProps {
  label?: string
  error?: string
  hint?: string
  children: ReactNode
  className?: string
}

export function Field({ label, error, hint, children, className }: FieldProps) {
  return (
    <div className={className}>
      {label && <label className="label-text">{label}</label>}
      {children}
      {hint && !error && <p className="mt-1 text-[11px] text-latte/40">{hint}</p>}
      {error && <p className="mt-1 text-[11px] text-red-300">{error}</p>}
    </div>
  )
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cx('input-field', props.className)} />
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cx('input-field resize-y', props.className)} />
}

export function Select({
  options,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { options: { value: string; label: string }[] }) {
  return (
    <select {...props} className={cx('input-field appearance-none', props.className)}>
      {options.map((o) => (
        <option key={o.value} value={o.value} className="bg-espresso text-latte">
          {o.label}
        </option>
      ))}
    </select>
  )
}

/* ------------------------------------------------------------------ badge */

export function StatusBadge({ status }: { status: DealStatus }) {
  const meta = STATUS_META[status]
  return (
    <span
      className="chip"
      style={{
        borderColor: `${meta.hex}66`,
        backgroundColor: `${meta.hex}1f`,
        color: meta.hex,
      }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: meta.hex }} />
      {meta.label}
    </span>
  )
}

export function TradeBadge({ trade }: { trade: 'export' | 'import' }) {
  const isExport = trade === 'export'
  return (
    <span
      className={cx(
        'chip',
        isExport
          ? 'border-gold/45 bg-gold/10 text-gold'
          : 'border-sky-400/45 bg-sky-400/10 text-sky-300',
      )}
    >
      {isExport ? '🌍 Export' : '📥 Import'}
    </span>
  )
}

export function PriorityBadge({ priority }: { priority: string }) {
  const map: Record<string, string> = {
    high: 'border-red-400/45 bg-red-400/10 text-red-300',
    medium: 'border-gold/45 bg-gold/10 text-gold',
    low: 'border-latte/25 bg-latte/5 text-latte/60',
  }
  return <span className={cx('chip', map[priority] ?? map.low)}>{priority}</span>
}

/* ------------------------------------------------------------------ modal */

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  subtitle?: string
  children: ReactNode
  width?: string
}

export function Modal({ open, onClose, title, subtitle, children, width = 'max-w-2xl' }: ModalProps) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 sm:p-6">
      <div
        onClick={onClose}
        className="animate-fade-in fixed inset-0 bg-bean/80 backdrop-blur-sm"
      />
      <div
        className={cx(
          'animate-scale-in relative z-10 my-8 w-full rounded-2xl border border-caramel/25 bg-espresso shadow-cup',
          width,
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-caramel/15 px-6 py-5">
          <div>
        <h3 className="text-xl text-latte">{title}</h3>
        {subtitle && <p className="mt-1 text-sm text-latte/50">{subtitle}</p>}
          </div>
          <button
        onClick={onClose}
        aria-label="Close"
        className="rounded-lg p-1.5 text-latte/50 transition hover:bg-latte/10 hover:text-latte"
          >
        <X size={18} />
          </button>
        </div>
        <div className="px-6 py-5">{children}</div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------ empty/loading */

export function EmptyState({
  emoji = '☕',
  title,
  hint,
  action,
}: {
  emoji?: string
  title: string
  hint?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-caramel/25 bg-espresso/25 px-6 py-14 text-center">
      {/*
        This emoji used to float up and down forever. Two of them render on the
        trade dashboard, and on WebKit that alone cost 393 ms per frame with the
        page otherwise idle — about 2 fps, on a screen where nothing was
        happening. Chromium composited it for free, which is why it only ever
        showed up on iPhones. It is decoration on an empty placeholder, so it
        simply sits still now.
      */}
      <div className="mb-3 text-4xl">{emoji}</div>
      <p className="font-display text-lg text-latte/85">{title}</p>
      {hint && <p className="mt-1.5 max-w-sm text-sm text-latte/45">{hint}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function Skeleton({ className }: { className?: string }) {
  // Pulsing opacity rather than a sliding gradient. The old version animated
  // `background-position`, which the compositor cannot handle on its own, so
  // every skeleton repainted 60 times a second — during loading, which is
  // exactly when the device has least to spare. Opacity animates on the
  // compositor and costs nothing.
  return <div className={cx('animate-pulse rounded-lg bg-caramel/15', className)} />
}

export function Spinner({ label = 'Brewing…' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-latte/55">
      <div className="relative h-10 w-10">
        <div className="absolute inset-0 rounded-full border-2 border-caramel/25" />
        <div className="absolute inset-0 animate-spin rounded-full border-2 border-transparent border-t-gold" />
      </div>
      <p className="text-sm">{label}</p>
    </div>
  )
}

/* --------------------------------------------------------------- confirm */

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Delete',
  onConfirm,
  onCancel,
}: {
  open: boolean
  title: string
  message: string
  confirmLabel?: string
  onConfirm: () => void
  onCancel: () => void
}) {
  const [busy, setBusy] = useState(false)

  const run = async () => {
    setBusy(true)
    try {
      await onConfirm()
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open={open} onClose={onCancel} title={title} width="max-w-md">
      <p className="text-sm leading-relaxed text-latte/70">{message}</p>
      <div className="mt-6 flex justify-end gap-3">
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button variant="danger" onClick={run} loading={busy}>
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  )
}
