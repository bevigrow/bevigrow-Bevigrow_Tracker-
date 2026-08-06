import { Lock } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { Button, Field, Input } from '../../components/ui'
import { ApiError, api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { AuthError, AuthShell } from './AuthShell'

export function ResetPassword() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const navigate = useNavigate()
  const { applySession } = useAuth()

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (!token) {
    return (
      <AuthShell
        title="Link not valid"
        subtitle="This reset link is missing its token"
        backTo="/login"
        backLabel="Back to sign in"
      >
        <p className="text-sm leading-relaxed text-latte/65">
          Open the link exactly as it was sent to you — copying only part of it drops the token
          that proves the request is yours.
        </p>
        <Link to="/forgot-password" className="btn-primary mt-6 w-full">
          Request a new link
        </Link>
      </AuthShell>
    )
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (password.length < 8) {
      setError('Use at least 8 characters.')
      return
    }
    if (password !== confirm) {
      setError('Those passwords do not match.')
      return
    }
    setBusy(true)
    try {
      // A successful reset signs the user straight in.
      const res = await api.resetPassword(token, password)
      applySession(res.access_token, res.user)
      navigate('/app', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reset your password.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell
      title="Choose a new password"
      subtitle="You'll be signed in once it's saved"
      backTo="/login"
      backLabel="Back to sign in"
    >
      <form onSubmit={submit} noValidate>
        <AuthError message={error} />

        <Field label="New password" hint="At least 8 characters" className="mb-4">
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

        <Field label="Confirm new password" className="mb-5">
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
          Save new password
        </Button>

        {error.includes('expired') && (
          <Link to="/forgot-password" className="btn-ghost mt-3 w-full">
            Request a new link
          </Link>
        )}
      </form>
    </AuthShell>
  )
}
