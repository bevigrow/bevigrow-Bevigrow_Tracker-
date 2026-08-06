import { motion } from 'framer-motion'
import { ArrowRight, Bot, Coffee, Globe2, ShieldCheck, Ship, Sparkles } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { AmbientParticles, Steam } from '../components/coffee/Ambient'

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

const STATS = [
  { value: '11', label: 'Pipeline stages' },
  { value: '5', label: 'Contact channels' },
  { value: 'AI', label: 'Written summaries' },
]

export function Landing() {
  const navigate = useNavigate()

  return (
    <div className="relative">
      <AmbientParticles density={26} />

      {/* ---------------------------------------------------------- hero */}
      <section className="relative flex min-h-screen flex-col items-center justify-center px-6 py-20">
        <div className="pointer-events-none absolute left-1/2 top-1/2 h-[30rem] w-[30rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-mocha/25 blur-[120px]" />

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          className="relative z-10 text-center"
        >
          <div className="relative mx-auto mb-8 w-fit">
            <div className="flex h-20 w-20 items-center justify-center rounded-3xl bg-gold-gradient shadow-cup">
              <Coffee size={38} className="text-bean" />
            </div>
            <Steam count={3} className="absolute -top-7 left-6" />
          </div>

          <p className="mb-4 text-xs uppercase tracking-[0.42em] text-gold">
            Est. Coffee Trading
          </p>
          <h1 className="font-display text-6xl leading-[0.95] text-latte sm:text-7xl md:text-8xl">
            Bevi<span className="text-gold">Grow</span>
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-balance text-base leading-relaxed text-latte/60 sm:text-lg">
            A premium export &amp; import management desk built for one thing — coffee.
          </p>

          <motion.button
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25, duration: 0.5 }}
            onClick={() => navigate('/login')}
            className="group mt-10 inline-flex items-center gap-3 rounded-full bg-gold-gradient px-9 py-4 text-base font-semibold text-bean shadow-cup transition hover:brightness-110 active:scale-[0.98]"
          >
            Enter BeviGrow Coffee B2B
            <ArrowRight size={19} className="transition-transform group-hover:translate-x-1" />
          </motion.button>

          {/* Quick proof points, so the fold says what the product is */}
          <div className="mx-auto mt-14 flex max-w-md flex-wrap items-center justify-center gap-x-10 gap-y-5">
            {STATS.map((s, i) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.4 + i * 0.08 }}
                className="text-center"
              >
                <p className="font-display text-3xl text-gold">{s.value}</p>
                <p className="mt-1 text-[11px] uppercase tracking-wider text-latte/40">
                  {s.label}
                </p>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </section>

      {/* -------------------------------------------------------- features */}
      <section className="relative z-10 mx-auto max-w-6xl px-6 pb-28">
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
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.45, delay: i * 0.06 }}
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
          initial={{ opacity: 0, scale: 0.97 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
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
