import { useEffect, useMemo, useRef } from 'react'

/** Slow-drifting coffee particles behind the app chrome. Canvas, not DOM, so
 *  hundreds of specks cost nothing in layout. */
export function AmbientParticles({ density = 34 }: { density?: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let raf = 0
    let width = 0
    let height = 0
    const dpr = Math.min(window.devicePixelRatio || 1, 2)

    type P = { x: number; y: number; r: number; vy: number; vx: number; a: number }
    let particles: P[] = []

    const seed = () => {
      particles = Array.from({ length: density }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        r: 0.8 + Math.random() * 2.2,
        vy: -(0.05 + Math.random() * 0.22),
        vx: (Math.random() - 0.5) * 0.14,
        a: 0.06 + Math.random() * 0.2,
      }))
    }

    const resize = () => {
      width = canvas.clientWidth
      height = canvas.clientHeight
      canvas.width = width * dpr
      canvas.height = height * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      seed()
    }

    const tick = () => {
      ctx.clearRect(0, 0, width, height)
      for (const p of particles) {
        p.y += p.vy
        p.x += p.vx
        if (p.y < -6) {
          p.y = height + 6
          p.x = Math.random() * width
        }
        if (p.x < -6) p.x = width + 6
        if (p.x > width + 6) p.x = -6

        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(217, 160, 91, ${p.a})`
        ctx.fill()
      }
      raf = requestAnimationFrame(tick)
    }

    resize()
    tick()
    window.addEventListener('resize', resize)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
    }
  }, [density])

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className="pointer-events-none fixed inset-0 z-0 h-full w-full opacity-70"
    />
  )
}

/** Steam wisps used beside headers and important notifications. */
export function Steam({ count = 3, className = '' }: { count?: number; className?: string }) {
  const delays = useMemo(
    () => Array.from({ length: count }, (_, i) => `${i * 0.85}s`),
    [count],
  )
  return (
    <div className={`pointer-events-none flex items-end gap-1.5 ${className}`} aria-hidden>
      {delays.map((d, i) => (
        <span
          key={i}
          className="block h-6 w-1 rounded-full bg-latte/30 blur-[2px] animate-steam"
          style={{ animationDelay: d }}
        />
      ))}
    </div>
  )
}
