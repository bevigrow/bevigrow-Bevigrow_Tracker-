import { KeyRound, Mail, ShieldCheck, UserCircle } from 'lucide-react'
import { useState } from 'react'

import { Button, Card, Field, Input } from '../components/ui'
import { ApiError, api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { formatDateTime, initials } from '../lib/format'
import { useToast } from '../lib/toast'

const ROLE_BLURB: Record<string, string> = {
  admin: 'Full access, including team management and application settings.',
  manager: 'Full access to all trading data. Cannot manage the team.',
  employee: 'Can log activity and manage the accounts they work on.',
}

export function Profile() {
  const { user, refreshUser } = useAuth()
  const toast = useToast()

  const [name, setName] = useState(user?.name ?? '')
  const [savingName, setSavingName] = useState(false)

  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [pwError, setPwError] = useState('')
  const [savingPw, setSavingPw] = useState(false)

  if (!user) return null
  const isGoogleOnly = user.auth_provider === 'google'

  const saveName = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      toast.error('Your name cannot be empty.')
      return
    }
    setSavingName(true)
    try {
      await api.updateProfile(name.trim())
      await refreshUser()
      toast.success('Profile updated.')
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Could not update your profile.')
    } finally {
      setSavingName(false)
    }
  }

  const savePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setPwError('')
    if (next.length < 8) {
      setPwError('Use at least 8 characters.')
      return
    }
    if (next !== confirm) {
      setPwError('Those passwords do not match.')
      return
    }
    setSavingPw(true)
    try {
      await api.changePassword(current, next)
      setCurrent('')
      setNext('')
      setConfirm('')
      await refreshUser()
      toast.success('☕ Password updated.')
    } catch (err) {
      setPwError(err instanceof ApiError ? err.message : 'Could not change your password.')
    } finally {
      setSavingPw(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="font-display text-3xl text-latte">Your Profile</h1>
        <p className="mt-1 text-sm text-latte/50">Manage your account details and password</p>
      </div>

      {/* ------------------------------------------------------- identity */}
      <Card>
        <div className="flex flex-wrap items-center gap-5">
          {user.avatar_url ? (
            <img
              src={user.avatar_url}
              alt=""
              className="h-16 w-16 rounded-full border border-caramel/30 object-cover"
              referrerPolicy="no-referrer"
            />
          ) : (
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-gold-gradient text-lg font-bold text-bean">
              {initials(user.name)}
            </div>
          )}
          <div className="min-w-0">
            <p className="font-display text-2xl text-latte">{user.name}</p>
            <p className="flex items-center gap-1.5 text-sm text-latte/50">
              <Mail size={13} /> {user.email}
            </p>
          </div>
          <div className="ml-auto text-right">
            <span className="chip border-gold/40 bg-gold/10 capitalize text-gold">
              <ShieldCheck size={11} /> {user.role}
            </span>
          </div>
        </div>

        <div className="mt-6 grid gap-4 border-t border-caramel/15 pt-5 sm:grid-cols-3">
          <div>
            <p className="text-[11px] uppercase tracking-wider text-latte/40">Sign-in method</p>
            <p className="mt-1 text-sm capitalize text-latte/85">
              {isGoogleOnly ? 'Google' : 'Email & password'}
            </p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wider text-latte/40">Last sign-in</p>
            <p className="mt-1 text-sm text-latte/85">{formatDateTime(user.last_login)}</p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wider text-latte/40">Member since</p>
            <p className="mt-1 text-sm text-latte/85">{formatDateTime(user.created_at)}</p>
          </div>
        </div>

        <p className="mt-4 rounded-lg border border-caramel/15 bg-bean/30 px-3.5 py-2.5 text-[12px] leading-relaxed text-latte/50">
          {ROLE_BLURB[user.role]} Only an administrator can change your role.
        </p>
      </Card>

      {/* ----------------------------------------------------------- name */}
      <Card>
        <h2 className="mb-4 flex items-center gap-2 font-display text-lg text-latte">
          <UserCircle size={17} className="text-gold" /> Display name
        </h2>
        <form onSubmit={saveName} noValidate className="flex flex-wrap items-end gap-3">
          <Field label="Full name" className="min-w-[240px] flex-1">
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Button type="submit" loading={savingName}>
            Save
          </Button>
        </form>
        <p className="mt-2 text-[11px] text-latte/40">
          Your email address is your sign-in identity and cannot be changed here — ask an
          administrator.
        </p>
      </Card>

      {/* ------------------------------------------------------- password */}
      <Card>
        <h2 className="mb-1 flex items-center gap-2 font-display text-lg text-latte">
          <KeyRound size={17} className="text-gold" />
          {isGoogleOnly ? 'Add a password' : 'Change password'}
        </h2>
        <p className="mb-4 text-[12px] text-latte/45">
          {isGoogleOnly
            ? 'You currently sign in with Google. Setting a password lets you sign in either way.'
            : 'Choose something at least 8 characters long.'}
        </p>

        <form onSubmit={savePassword} noValidate className="space-y-4">
          {pwError && (
            <p className="rounded-lg border border-red-400/30 bg-red-500/10 px-3.5 py-2.5 text-sm text-red-300" role="alert">
              {pwError}
            </p>
          )}

          {!isGoogleOnly && (
            <Field label="Current password">
              <Input
                type="password"
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                autoComplete="current-password"
                placeholder="••••••••"
              />
            </Field>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="New password" hint="At least 8 characters">
              <Input
                type="password"
                value={next}
                onChange={(e) => setNext(e.target.value)}
                autoComplete="new-password"
                placeholder="••••••••"
              />
            </Field>
            <Field label="Confirm new password">
              <Input
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                autoComplete="new-password"
                placeholder="••••••••"
              />
            </Field>
          </div>

          <Button type="submit" loading={savingPw}>
            {isGoogleOnly ? 'Set password' : 'Update password'}
          </Button>
        </form>
      </Card>
    </div>
  )
}
