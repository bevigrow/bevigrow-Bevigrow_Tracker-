import { Mail } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { Button, Field, Input } from '../../components/ui'
import { ApiError, api } from '../../lib/api'
import { AuthError, AuthNotice, AuthShell } from './AuthShell'

export function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [sent, setSent] = useState<{ message: string; email_sent: boolean } | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
      setError('Enter a valid email address.')
      return
    }
    setBusy(true)
    try {
      setSent(await api.forgotPassword(email.trim()))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not start the reset.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell
      title="Reset your password"
      subtitle="We'll send a link to set a new one"
      backTo="/login"
      backLabel="Back to sign in"
      footer={
        <>
          Remembered it?{' '}
          <Link to="/login" className="text-gold hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      {sent ? (
        <div>
          <AuthNotice message={sent.message} />
          {!sent.email_sent && (
            <p className="rounded-lg border border-caramel/20 bg-bean/40 px-3.5 py-3 text-[12px] leading-relaxed text-latte/55">
              This workspace has no email provider configured, so no message can be delivered.
              Ask your BeviGrow administrator to set a new password for you from the Team page
              — it takes a few seconds.
            </p>
          )}
          <Link to="/login" className="btn-ghost mt-5 w-full">
            Back to sign in
          </Link>
        </div>
      ) : (
        <form onSubmit={submit} noValidate>
          <AuthError message={error} />
          <p className="mb-5 text-sm leading-relaxed text-latte/55">
            Enter the email address on your BeviGrow account and we'll send a link to choose a
            new password. The link expires in one hour.
          </p>

          <Field label="Email address" className="mb-5">
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
                autoComplete="username"
              />
            </div>
          </Field>

          <Button type="submit" loading={busy} className="w-full py-3">
            Send reset link
          </Button>
        </form>
      )}
    </AuthShell>
  )
}
