import { AnimatePresence, motion } from 'framer-motion'
import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

type ToastKind = 'success' | 'error' | 'info'

interface Toast {
  id: number
  kind: ToastKind
  message: string
}

interface ToastApi {
  success: (message: string) => void
  error: (message: string) => void
  info: (message: string) => void
}

const ToastContext = createContext<ToastApi | null>(null)

const STYLES: Record<ToastKind, { border: string; icon: string; accent: string }> = {
  success: { border: 'border-emerald-400/45', icon: '☕', accent: 'bg-emerald-400' },
  error: { border: 'border-red-400/45', icon: '⚠️', accent: 'bg-red-400' },
  info: { border: 'border-gold/45', icon: '🌍', accent: 'bg-gold' },
}

let nextId = 1

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const push = useCallback((kind: ToastKind, message: string) => {
    const id = nextId++
    setToasts((prev) => [...prev, { id, kind, message }])
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 4200)
  }, [])

  const api = useMemo<ToastApi>(
    () => ({
      success: (m) => push('success', m),
      error: (m) => push('error', m),
      info: (m) => push('info', m),
    }),
    [push],
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div // w-80 plus the 1.5rem inset overflows a 320px screen, so cap it.
        className="pointer-events-none fixed bottom-6 right-6 z-[100] flex w-[min(20rem,calc(100vw-3rem))] flex-col gap-3">
        <AnimatePresence initial={false}>
          {toasts.map((t) => (
            <motion.div
              key={t.id}
              layout
              initial={{ opacity: 0, x: 60, scale: 0.94 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 60, scale: 0.94 }}
              transition={{ type: 'spring', stiffness: 380, damping: 30 }}
              className={`pointer-events-auto relative overflow-hidden rounded-xl border ${STYLES[t.kind].border} bg-espresso/95 p-4 pl-5 shadow-cup backdrop-blur`}
            >
              <span className={`absolute inset-y-0 left-0 w-1 ${STYLES[t.kind].accent}`} />
              {/* Steam wisps drifting off the notification */}
              {t.kind === 'success' && (
                <span className="pointer-events-none absolute -top-1 left-8 h-6 w-1.5 rounded-full bg-latte/25 blur-[2px] animate-steam" />
              )}
              <div className="flex items-start gap-2.5">
                <span className="text-base leading-none">{STYLES[t.kind].icon}</span>
                <p className="text-sm leading-snug text-latte/90">{t.message}</p>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>')
  return ctx
}
