/**
 * "Sign in with Google" using Google Identity Services.
 *
 * The GIS script is loaded on demand rather than in index.html, so a
 * deployment with no Google client ID never contacts Google at all. The
 * browser receives a signed ID token which is sent to our backend; the backend
 * verifies the signature and audience before trusting a single field of it.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

const GIS_SRC = 'https://accounts.google.com/gsi/client'

interface GoogleCredentialResponse {
  credential?: string
}

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (o: {
            client_id: string
            callback: (r: GoogleCredentialResponse) => void
            auto_select?: boolean
            cancel_on_tap_outside?: boolean
          }) => void
          renderButton: (el: HTMLElement, o: Record<string, unknown>) => void
        }
      }
    }
  }
}

let scriptPromise: Promise<void> | null = null

function loadGis(): Promise<void> {
  if (scriptPromise) return scriptPromise
  scriptPromise = new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) return resolve()
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GIS_SRC}"]`)
    if (existing) {
      existing.addEventListener('load', () => resolve())
      existing.addEventListener('error', () => reject(new Error('load failed')))
      return
    }
    const script = document.createElement('script')
    script.src = GIS_SRC
    script.async = true
    script.defer = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('Could not load Google sign-in.'))
    document.head.appendChild(script)
  })
  return scriptPromise
}

export function GoogleSignIn({
  clientId,
  onCredential,
  onError,
  disabled = false,
}: {
  clientId: string
  onCredential: (credential: string) => void
  onError: (message: string) => void
  disabled?: boolean
}) {
  const holder = useRef<HTMLDivElement>(null)
  const [ready, setReady] = useState(false)
  const [failed, setFailed] = useState(false)

  // Keep the latest callbacks without re-initialising GIS on every render.
  const cbRef = useRef({ onCredential, onError })
  cbRef.current = { onCredential, onError }

  const mount = useCallback(() => {
    const gis = window.google?.accounts?.id
    if (!gis || !holder.current) return
    gis.initialize({
      client_id: clientId,
      callback: (res) => {
        if (res.credential) cbRef.current.onCredential(res.credential)
        else cbRef.current.onError('Google did not return a sign-in credential.')
      },
      auto_select: false,
      cancel_on_tap_outside: true,
    })
    holder.current.innerHTML = ''
    gis.renderButton(holder.current, {
      theme: 'filled_black',
      size: 'large',
      shape: 'pill',
      text: 'signin_with',
      logo_alignment: 'left',
      width: 320,
    })
    setReady(true)
  }, [clientId])

  useEffect(() => {
    if (!clientId) return
    let cancelled = false
    loadGis()
      .then(() => {
        if (!cancelled) mount()
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [clientId, mount])

  if (!clientId) return null

  if (failed) {
    return (
      <p className="rounded-lg border border-caramel/20 bg-bean/40 px-3 py-2 text-center text-[11px] text-latte/50">
        Google sign-in could not load. Use your email and password below.
      </p>
    )
  }

  return (
    <div className={disabled ? 'pointer-events-none opacity-50' : ''}>
      {/* GIS renders its own iframe button here. */}
      <div ref={holder} className="flex justify-center" />
      {!ready && (
        <div className="h-10 animate-pulse rounded-full border border-caramel/20 bg-bean/40" />
      )}
    </div>
  )
}
