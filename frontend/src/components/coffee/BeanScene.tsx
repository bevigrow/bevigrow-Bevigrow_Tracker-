/**
 * The landing bean: a cinematic 3D scene where the device can afford it, and a
 * CSS-only bean everywhere else.
 *
 * Three.js costs ~950 kB of parse on top of ~260 kB over the wire. On a phone
 * that is the dominant cost of the whole landing page, so it is loaded lazily
 * and only when `shouldRender3D()` says the device is up to it. On everything
 * else the import never happens, so the bytes are never fetched at all.
 */
import { Suspense, lazy, useEffect, useState } from 'react'

export type Phase = 'idle' | 'cracking' | 'open'

const Bean3D = lazy(() => import('./Bean3D'))

function hasWebGL(): boolean {
  try {
    const canvas = document.createElement('canvas')
    return !!(
      window.WebGLRenderingContext &&
      (canvas.getContext('webgl') || canvas.getContext('experimental-webgl'))
    )
  } catch {
    return false
  }
}

/**
 * Whether this device should download and run the Three.js scene.
 *
 * Phones are excluded deliberately — not because they cannot render it, but
 * because the parse cost delays the first paint of the page they actually came
 * for. The CSS bean animates the same beat at a fraction of the price.
 */
function shouldRender3D(): boolean {
  if (typeof window === 'undefined') return false
  if (!hasWebGL()) return false

  // Someone who asked for less motion should not be served a 3D scene.
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false

  // Respect an explicit request to save data.
  const conn = (navigator as Navigator & { connection?: { saveData?: boolean; effectiveType?: string } })
    .connection
  if (conn?.saveData) return false
  if (conn?.effectiveType && /(^|-)2g$/.test(conn.effectiveType)) return false

  // Touch-primary and narrow: a phone. Tablets and touch laptops are wide
  // enough to keep the full scene.
  const isPhone =
    window.matchMedia('(pointer: coarse)').matches && window.innerWidth < 1024
  if (isPhone) return false

  // Very low core counts mean parsing a megabyte of JS will hurt.
  if ((navigator.hardwareConcurrency ?? 8) <= 2) return false

  return true
}

/** Pure-CSS bean: no WebGL, no Three.js, no download. */
function CssBean({ phase, onCrack }: { phase: Phase; onCrack: () => void }) {
  const open = phase !== 'idle'
  return (
    <div
      onClick={onCrack}
      className="flex h-full w-full cursor-pointer items-center justify-center"
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onCrack()}
      aria-label="Crack the coffee bean"
    >
      <div className="relative h-64 w-48">
        {[1, -1].map((side) => (
          <div
            key={side}
            className="absolute top-0 h-64 w-24 transition-all duration-1000 ease-out"
            style={{
              left: side === 1 ? '50%' : 0,
              transform: `translateX(${open ? side * 70 : 0}px) rotate(${open ? side * 22 : 0}deg)`,
              opacity: open ? 0.85 : 1,
              background: 'linear-gradient(135deg, #6f4e37, #3b2416 60%, #2a1a12)',
              borderRadius:
                side === 1 ? '0 100% 100% 0 / 0 50% 50% 0' : '100% 0 0 100% / 50% 0 0 50%',
              boxShadow: 'inset 0 0 40px rgba(0,0,0,0.5)',
            }}
          />
        ))}
        {/* The crease, so the silhouette still reads as a coffee bean. */}
        <div
          className="absolute left-1/2 top-2 h-60 w-1.5 -translate-x-1/2 rounded-full bg-bean/80 transition-opacity duration-700"
          style={{ opacity: open ? 0 : 0.9 }}
        />
        <div
          className="absolute left-1/2 top-1/2 h-24 w-24 -translate-x-1/2 -translate-y-1/2 rounded-full bg-gold blur-2xl transition-opacity duration-700"
          style={{ opacity: open ? 0.75 : 0 }}
        />
      </div>
    </div>
  )
}

export function BeanScene({ phase, onCrack }: { phase: Phase; onCrack: () => void }) {
  // null until the capability check runs, so the server-rendered/first frame
  // never guesses wrong and swaps the bean out underneath the user.
  const [use3D, setUse3D] = useState<boolean | null>(null)
  useEffect(() => setUse3D(shouldRender3D()), [])

  if (use3D === null) return null
  if (!use3D) return <CssBean phase={phase} onCrack={onCrack} />

  return (
    <Suspense fallback={<CssBean phase={phase} onCrack={onCrack} />}>
      <Bean3D phase={phase} onCrack={onCrack} />
    </Suspense>
  )
}
