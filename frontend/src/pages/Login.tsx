import { Eye, EyeOff, Lock, Mail } from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import { GoogleSignIn } from '../components/GoogleSignIn'
import { Button, Field, Input } from '../components/ui'
import { ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import { AuthError, AuthShell, OrDivider } from './auth/AuthShell'

export function Login() {
  const { login, loginWithGoogle, user, loading, config } = useAuth()
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

  const onGoogle = async (credential: string) => {
    setError('')
    setBusy(true)
    try {
      await loginWithGoogle(credential)
      navigate('/app', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Google sign-in failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to the BeviGrow coffee trading desk"
      footer={
        config?.self_signup_enabled ? (
          <>
            New here?{' '}
            <Link to="/signup" className="text-gold hover:underline">
              Create an account
            </Link>
          </>
        ) : (
          'Accounts are created by your BeviGrow administrator.'
        )
      }
    >
      {config?.google_enabled && (
        <>
          <GoogleSignIn
            clientId={config.google_client_id}
            onCredential={onGoogle}
            onError={setError}
            disabled={busy}
          />
          <OrDivider label="or use your email" />
        </>
      )}

      <form onSubmit={submit} noValidate>
        <AuthError message={error} />

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

        <Field label="Password" className="mb-2">
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

        <div className="mb-5 text-right">
          <Link to="/forgot-password" className="text-xs text-gold/80 hover:text-gold hover:underline">
            Forgot your password?
          </Link>
        </div>

        <Button type="submit" loading={busy} className="w-full py-3">
          {busy ? 'Brewing your session…' : 'Sign in'}
        </Button>
      </form>
    </AuthShell>
  )
}
