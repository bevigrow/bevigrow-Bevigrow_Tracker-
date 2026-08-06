import { Lock, Mail, User as UserIcon } from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import { GoogleSignIn } from '../../components/GoogleSignIn'
import { Button, Field, Input } from '../../components/ui'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { AuthError, AuthShell, OrDivider } from './AuthShell'

export function SignUp() {
  const { signup, loginWithGoogle, user, loading, config } = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)

  if (!loading && user) return <Navigate to="/app" replace />

  // Sign-up is invite-only unless the server enables it.
  if (config && !config.self_signup_enabled) {
    return (
      <AuthShell
        title="Invitation only"
        subtitle="BeviGrow accounts are created by an administrator"
        backTo="/login"
        backLabel="Back to sign in"
      >
        <p className="text-sm leading-relaxed text-latte/65">
          Self sign-up is turned off for this workspace. Ask your BeviGrow administrator to
          create an account for you — they can add you from the Team page in seconds.
        </p>
        <Link to="/login" className="btn-primary mt-6 w-full">
          Back to sign in
        </Link>
      </AuthShell>
    )
  }

  const validate = () => {
    const e: Record<string, string> = {}
    if (!name.trim()) e.name = 'Your name is required'
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) e.email = 'Enter a valid email address'
    if (password.length < 8) e.password = 'Use at least 8 characters'
    if (password !== confirm) e.confirm = 'Passwords do not match'
    setFieldErrors(e)
    return Object.keys(e).length === 0
  }

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault()
    setError('')
    if (!validate()) return
    setBusy(true)
    try {
      await signup(name.trim(), email.trim(), password)
      navigate('/app', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create your account.')
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
      setError(err instanceof ApiError ? err.message : 'Google sign-up failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell
      title="Create your account"
      subtitle="Join the BeviGrow coffee trading desk"
      backTo="/login"
      backLabel="Back to sign in"
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" className="text-gold hover:underline">
            Sign in
          </Link>
        </>
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

        {config?.allowed_email_domains.length ? (
          <p className="mb-4 rounded-lg border border-caramel/20 bg-bean/40 px-3 py-2 text-[11px] text-latte/50">
            Only {config.allowed_email_domains.map((d) => `@${d}`).join(', ')} addresses may
            register.
          </p>
        ) : null}

        <Field label="Full name" error={fieldErrors.name} className="mb-4">
          <div className="relative">
            <UserIcon
              size={16}
              className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-latte/35"
            />
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Priya Sharma"
              className="pl-10"
              autoComplete="name"
            />
          </div>
        </Field>

        <Field label="Email address" error={fieldErrors.email} className="mb-4">
          <div className="relative">
            <Mail
              size={16}
              className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-latte/35"
            />
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@bevigrow.com"
              className="pl-10"
              autoComplete="email"
            />
          </div>
        </Field>

        <Field
          label="Password"
          error={fieldErrors.password}
          hint="At least 8 characters"
          className="mb-4"
        >
          <div className="relative">
            <Lock
              size={16}
              className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-latte/35"
            />
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="pl-10"
              autoComplete="new-password"
            />
          </div>
        </Field>

        <Field label="Confirm password" error={fieldErrors.confirm} className="mb-5">
          <div className="relative">
            <Lock
              size={16}
              className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-latte/35"
            />
            <Input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="••••••••"
              className="pl-10"
              autoComplete="new-password"
            />
          </div>
        </Field>

        <Button type="submit" loading={busy} className="w-full py-3">
          Create account
        </Button>
      </form>
    </AuthShell>
  )
}
