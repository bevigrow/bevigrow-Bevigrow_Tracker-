import { motion } from 'framer-motion'
import { ArrowLeft, Coffee, Eye, EyeOff, Lock, Mail } from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import { AmbientParticles, Steam } from '../components/coffee/Ambient'
import { Button, Field, Input } from '../components/ui'
import { ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'

export function Login() {
  const { login, user, loading } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (!loading && user) return <Navigate to="/app" replace />

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await login(email.trim(), password)
      navigate('/app', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Sign-in failed. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center px-5 py-12">
      <AmbientParticles density={30} />
      <div className="pointer-events-none absolute left-1/2 top-1/3 h-96 w-96 -translate-x-1/2 rounded-full bg-mocha/25 blur-[110px]" />

      <Link
        to="/"
        className="absolute left-6 top-6 z-10 inline-flex items-center gap-2 text-sm text-latte/50 transition hover:text-latte"
      >
        <ArrowLeft size={16} />
        Back
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
          <h1 className="font-display text-4xl text-latte">Welcome back</h1>
          <p className="mt-2 text-sm text-latte/50">
            Sign in to the BeviGrow coffee trading desk
          </p>
        </div>

        <form
          onSubmit={submit}
          className="rounded-2xl border border-caramel/20 bg-espresso/60 p-7 shadow-cup backdrop-blur-xl"
        >
          <Field label="Email address" className="mb-4">
            <div className="relative">
              <Mail
                size={16}
                className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-latte/35"
              />
              <Input
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@bevigrow.com"
                className="pl-10"
              />
            </div>
          </Field>

          <Field label="Password" className="mb-5">
            <div className="relative">
              <Lock
                size={16}
                className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-latte/35"
              />
              <Input
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="pl-10 pr-11"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-latte/40 transition hover:text-latte/80"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </Field>

          {error && (
            <motion.p
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-4 rounded-lg border border-red-400/30 bg-red-500/10 px-3.5 py-2.5 text-sm text-red-300"
              role="alert"
            >
              {error}
            </motion.p>
          )}

          <Button type="submit" loading={busy} className="w-full py-3">
            {busy ? 'Brewing your session…' : 'Sign in'}
          </Button>
        </form>

        <p className="mt-6 text-center text-xs text-latte/30">
          Trouble signing in? Contact your BeviGrow administrator.
        </p>
      </motion.div>
    </div>
  )
}
