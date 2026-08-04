import { AnimatePresence, motion } from 'framer-motion'
import { ArrowRight, Bot, Globe2, ShieldCheck, Ship, Sparkles } from 'lucide-react'
import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { BeanScene } from '../components/coffee/BeanScene'
import type { Phase } from '../components/coffee/BeanScene'
import { AmbientParticles } from '../components/coffee/Ambient'
import { PourScene } from '../components/coffee/PourScene'

const FEATURES = [
  {
    icon: Globe2,
    title: 'Global Trade Desk',
    body: 'Track every export and import conversation by country, product and roast profile — one record per account, from first contact to final delivery.',
  },
  {
    icon: Bot,
    title: 'AI Interaction Summaries',
    body: 'Type shorthand notes after a call; Claude Haiku returns a clean, professional summary ready for the record. Fast, and inexpensive enough to use on every entry.',
  },
  {
    icon: Ship,
    title: 'Shipment Pipeline',
    body: 'Eleven stages from new lead to completed order, on a board you can read at a glance and move deals through in one click.',
  },
  {
    icon: ShieldCheck,
    title: 'Proof on File',
    body: 'Quotations, invoices, purchase orders, meeting screenshots and sample photos — attached to the account they belong to.',
  },
]

export function Landing() {
  const navigate = useNavigate()
  const [phase, setPhase] = useState<Phase>('idle')

  const crack = useCallback(() => {
    setPhase((p) => {
      if (p !== 'idle') return p
      window.setTimeout(() => setPhase('open'), 900)
      return 'cracking'
    })
  }, [])

  const revealed = phase === 'open'

  return (
    <div className="relative">
      <AmbientParticles density={40} />

      {/* ---------------------------------------------------------- intro */}
      <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6">
        <div className="pointer-events-none absolute left-1/2 top-1/2 h-[34rem] w-[34rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-mocha/25 blur-[120px]" />

        {/* Once the bean is open the logo takes the stage, so the scene recedes
            into a soft backdrop rather than competing with the wordmark. */}
        <motion.div
          className="absolute inset-0 z-10"
          animate={{ opacity: revealed ? 0.16 : 1, scale: revealed ? 1.12 : 1 }}
          transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1] }}
          style={{ pointerEvents: revealed ? 'none' : 'auto' }}
        >
          <BeanScene phase={phase} onCrack={crack} />
        </motion.div>

        {/* Prompt before the crack */}
        <AnimatePresence>
          {!revealed && (
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ delay: 0.5, duration: 0.7 }}
              className="pointer-events-none relative z-20 mt-[24rem] text-center"
            >
              <p className="font-display text-2xl text-latte/80 sm:text-3xl">
                One bean. One trading floor.
              </p>
              <p className="mt-3 text-sm uppercase tracking-[0.32em] text-gold/70">
                Click or drag the bean to open
              </p>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Reveal after the crack */}
        <AnimatePresence>
          {revealed && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 30 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
              className="relative z-20 text-center"
            >
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.2 }}
                className="mb-4 text-xs uppercase tracking-[0.42em] text-gold"
              >
                Est. Coffee Trading
              </motion.p>
              <h1 className="font-display text-6xl leading-[0.95] text-latte sm:text-7xl md:text-8xl">
                Bevi<span className="text-gold">Grow</span>
              </h1>
              <p className="mx-auto mt-6 max-w-xl text-balance text-base leading-relaxed text-latte/60 sm:text-lg">
                A premium export &amp; import management desk built for one thing — coffee.
              </p>

              <motion.button
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.45 }}
                onClick={() => navigate('/login')}
                className="group mt-10 inline-flex items-center gap-3 rounded-full bg-gold-gradient px-9 py-4 text-base font-semibold text-bean shadow-cup transition hover:brightness-110 active:scale-[0.98]"
              >
                Enter BeviGrow Coffee B2B
                <ArrowRight size={19} className="transition-transform group-hover:translate-x-1" />
              </motion.button>

              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.8 }}
                className="mt-10 text-[11px] uppercase tracking-[0.3em] text-latte/30"
              >
                Scroll to brew
              </motion.p>
            </motion.div>
          )}
        </AnimatePresence>
      </section>

      {/* ------------------------------------------------------ pour scene */}
      <section className="relative z-10">
        <div className="mx-auto max-w-3xl px-6 pb-4 pt-24 text-center">
          <p className="mb-3 text-xs uppercase tracking-[0.34em] text-gold/70">The Process</p>
          <h2 className="font-display text-4xl text-latte sm:text-5xl">
            Every great cup is built in layers
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-balance text-latte/55">
            So is every closed order. Scroll to watch it come together.
          </p>
        </div>
        <PourScene />
      </section>

      {/* -------------------------------------------------------- features */}
      <section className="relative z-10 mx-auto max-w-6xl px-6 py-28">
        <div className="mb-14 text-center">
          <p className="mb-3 text-xs uppercase tracking-[0.34em] text-gold/70">The Platform</p>
          <h2 className="font-display text-4xl text-latte sm:text-5xl">
            Built for coffee traders, not generic CRM
          </h2>
        </div>

        <div className="grid gap-6 sm:grid-cols-2">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.55, delay: i * 0.08 }}
              className="glass group rounded-2xl p-7 transition-all duration-300 hover:border-gold/35"
            >
              <div className="mb-5 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-gold/12 text-gold transition group-hover:bg-gold/20">
                <f.icon size={22} />
              </div>
              <h3 className="mb-2.5 font-display text-2xl text-latte">{f.title}</h3>
              <p className="text-sm leading-relaxed text-latte/55">{f.body}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ------------------------------------------------------------- cta */}
      <section className="relative z-10 mx-auto max-w-4xl px-6 pb-32">
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="relative overflow-hidden rounded-3xl border border-gold/25 bg-roast-gradient p-12 text-center shadow-cup"
        >
          <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-gold/20 blur-3xl" />
          <Sparkles className="mx-auto mb-5 text-gold" size={30} />
          <h2 className="font-display text-4xl text-latte">Your trading floor is ready</h2>
          <p className="mx-auto mt-4 max-w-md text-latte/60">
            Sign in to log today's calls, chase quotations, and watch the pipeline move.
          </p>
          <button
            onClick={() => navigate('/login')}
            className="mt-9 inline-flex items-center gap-3 rounded-full bg-gold-gradient px-9 py-4 font-semibold text-bean shadow-lift transition hover:brightness-110 active:scale-[0.98]"
          >
            Enter BeviGrow Coffee B2B
            <ArrowRight size={18} />
          </button>
        </motion.div>

        <p className="mt-12 text-center text-xs text-latte/25">
          © {new Date().getFullYear()} BeviGrow. Coffee export &amp; import management.
        </p>
      </section>
    </div>
  )
}
