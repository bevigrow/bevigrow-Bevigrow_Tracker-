import { motion } from 'framer-motion'
import { ArrowLeft, Coffee } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { AmbientParticles, Steam } from '../../components/coffee/Ambient'

/** Shared frame for every unauthenticated page, so they read as one product. */
export function AuthShell({
  title,
  subtitle,
  children,
  footer,
  backTo = '/',
  backLabel = 'Back',
}: {
  title: string
  subtitle?: string
  children: ReactNode
  footer?: ReactNode
  backTo?: string
  backLabel?: string
}) {
  return (
    <div className="relative flex min-h-screen items-center justify-center px-5 py-12">
      <AmbientParticles density={30} />
      <div className="pointer-events-none absolute left-1/2 top-1/3 h-96 w-96 -translate-x-1/2 rounded-full bg-mocha/25 blur-[110px]" />

      <Link
        to={backTo}
        className="absolute left-6 top-6 z-10 inline-flex items-center gap-2 text-sm text-latte/50 transition hover:text-latte"
      >
        <ArrowLeft size={16} />
        {backLabel}
      </Link>

      <motion.div
        initial={{ opacity: 0, y: 26 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="relative z-10 w-full max-w-md"
      >
        <div className="mb-8 text-center">
          <div className="relative mx-auto mb-5 w-fit">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gold-gradient shadow-cup">
              <Coffee size={30} className="text-bean" />
            </div>
            <Steam count={3} className="absolute -top-6 left-4" />
          </div>
          <h1 className="font-display text-4xl text-latte">{title}</h1>
          {subtitle && <p className="mt-2 text-sm text-latte/50">{subtitle}</p>}
        </div>

        <div className="rounded-2xl border border-caramel/20 bg-espresso/60 p-7 shadow-cup backdrop-blur-xl">
          {children}
        </div>

        {footer && <div className="mt-6 text-center text-sm text-latte/45">{footer}</div>}
      </motion.div>
    </div>
  )
}

export function AuthError({ message }: { message: string }) {
  if (!message) return null
  return (
    <motion.p
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-4 rounded-lg border border-red-400/30 bg-red-500/10 px-3.5 py-2.5 text-sm text-red-300"
      role="alert"
    >
      {message}
    </motion.p>
  )
}

export function AuthNotice({ message }: { message: string }) {
  if (!message) return null
  return (
    <motion.p
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-4 rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-3.5 py-2.5 text-sm text-emerald-200"
      role="status"
    >
      {message}
    </motion.p>
  )
}

export function OrDivider({ label = 'or' }: { label?: string }) {
  return (
    <div className="my-5 flex items-center gap-3">
      <span className="h-px flex-1 bg-caramel/20" />
      <span className="text-[11px] uppercase tracking-widest text-latte/35">{label}</span>
      <span className="h-px flex-1 bg-caramel/20" />
    </div>
  )
}
