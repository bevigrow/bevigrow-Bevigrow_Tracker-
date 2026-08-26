import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { api, onUnauthorized, tokenStore } from './api'
import type { AuthConfig, User } from './types'

interface AuthState {
  user: User | null
  loading: boolean
  /** Public server config: which sign-in methods to offer. */
  config: AuthConfig | null
  login: (email: string, password: string) => Promise<void>
  loginWithGoogle: (credential: string) => Promise<void>
  signup: (name: string, email: string, password: string) => Promise<void>
  applySession: (token: string, user: User) => void
  refreshUser: () => Promise<void>
  logout: () => void
  isAdmin: boolean
  isManager: boolean
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [config, setConfig] = useState<AuthConfig | null>(null)
  const [loading, setLoading] = useState(true)

  // Restore the session from a stored token on first mount.
  // If there's no token, stop loading immediately so the login page renders fast.
  useEffect(() => {
    let cancelled = false
    const token = tokenStore.get()
    if (!token) {
      setLoading(false)
      return
    }
    // Token exists — verify it asynchronously without blocking the UI
    api
      .me()
      .then((u) => {
        if (!cancelled) setUser(u)
      })
      .catch(() => tokenStore.clear())
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Which sign-in methods the server offers. Public, so it can load before login.
  useEffect(() => {
    let cancelled = false
    api
      .authConfig()
      .then((c) => {
        if (!cancelled) setConfig(c)
      })
      .catch(() => {
        // A server that cannot report its config still supports password login.
        if (!cancelled)
          setConfig({
            google_enabled: false,
            google_client_id: '',
            self_signup_enabled: false,
            password_reset_enabled: true,
            allowed_email_domains: [],
          })
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Any 401 from anywhere in the app drops us back to the login screen.
  useEffect(() => onUnauthorized(() => setUser(null)), [])

  const applySession = useCallback((token: string, nextUser: User) => {
    tokenStore.set(token)
    setUser(nextUser)
  }, [])

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await api.login(email, password)
      applySession(res.access_token, res.user)
    },
    [applySession],
  )

  const loginWithGoogle = useCallback(
    async (credential: string) => {
      const res = await api.loginWithGoogle(credential)
      applySession(res.access_token, res.user)
    },
    [applySession],
  )

  const signup = useCallback(
    async (name: string, email: string, password: string) => {
      const res = await api.signup(name, email, password)
      applySession(res.access_token, res.user)
    },
    [applySession],
  )

  /** Re-read the current user after a profile change. */
  const refreshUser = useCallback(async () => {
    setUser(await api.me())
  }, [])

  const logout = useCallback(() => {
    tokenStore.clear()
    setUser(null)
  }, [])

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      config,
      login,
      loginWithGoogle,
      signup,
      applySession,
      refreshUser,
      logout,
      isAdmin: user?.role === 'admin',
      isManager: user?.role === 'admin' || user?.role === 'manager',
    }),
    [user, loading, config, login, loginWithGoogle, signup, applySession, refreshUser, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
