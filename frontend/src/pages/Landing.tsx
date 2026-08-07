import { motion } from 'framer-motion'
import { ArrowRight, Coffee } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { AmbientParticles, Steam } from '../components/coffee/Ambient'

/** A single screen: the mark, the name, and the way in. Nothing else. */
export function Landing() {
  const navigate = useNavigate()

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-6">
      <AmbientParticles density={26} />

      {/* Sized against the viewport so it can never widen the page. */}
      <div className="pointer-events-none absolute left-1/2 top-1/2 h-[80vw] w-[80vw] max-h-[30rem] max-w-[30rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-mocha/25 blur-[120px]" />

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

        <p className="mb-4 text-xs uppercase tracking-[0.42em] text-gold">Est. Coffee Trading</p>

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
      </motion.div>

      <p className="absolute bottom-6 left-1/2 -translate-x-1/2 text-center text-[11px] text-latte/25">
        © {new Date().getFullYear()} BeviGrow. Coffee export &amp; import management.
      </p>
    </div>
  )
}
