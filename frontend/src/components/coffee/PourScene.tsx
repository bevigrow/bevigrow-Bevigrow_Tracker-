/**
 * Scroll-driven cappuccino build.
 *
 * A transparent glass cup stays pinned centre-screen. As the user scrolls, an
 * animated hand enters from off-screen and pours, in sequence: coffee powder,
 * hot water, milk, foam, and a dusting of cocoa. Each ingredient's liquid layer
 * grows inside the cup, with steam rising once the drink is hot.
 *
 * GSAP ScrollTrigger drives everything on a single scrubbed timeline so the
 * animation tracks the scrollbar exactly, forwards and backwards.
 */
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { useLayoutEffect, useRef } from 'react'

gsap.registerPlugin(ScrollTrigger)

interface Step {
  key: string
  label: string
  caption: string
  color: string
  /** Cumulative fill height (0–1 of the cup's interior) once this step ends. */
  fill: number
  pourColor: string
}

const STEPS: Step[] = [
  {
    key: 'powder',
    label: 'Ground Coffee',
    caption: 'Freshly roasted Arabica, ground to an espresso fineness.',
    color: '#4A2F1D',
    fill: 0.16,
    pourColor: '#5A3A24',
  },
  {
    key: 'water',
    label: 'Hot Water',
    caption: 'Ninety-three degrees — hot enough to extract, gentle enough not to scorch.',
    color: '#6F4E37',
    fill: 0.5,
    pourColor: '#8B5E3C',
  },
  {
    key: 'milk',
    label: 'Steamed Milk',
    caption: 'Poured slowly against the wall of the glass for a clean layer.',
    color: '#C9A57E',
    fill: 0.78,
    pourColor: '#EFE2D0',
  },
  {
    key: 'foam',
    label: 'Micro Foam',
    caption: 'A dense, glossy crown of microfoam.',
    color: '#F0E2CD',
    fill: 0.94,
    pourColor: '#FBF5EC',
  },
  {
    key: 'cocoa',
    label: 'Cocoa Dust',
    caption: 'A final dusting. Your cappuccino — and your pipeline — is ready.',
    color: '#8B5E3C',
    fill: 0.94,
    pourColor: '#5A3A24',
  },
]

const CUP = { x: 120, yTop: 70, yBottom: 330, wTop: 160, wBottom: 116 }

export function PourScene() {
  const root = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    const el = root.current
    if (!el) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      // Show the finished drink without any scroll choreography.
      STEPS.forEach((s) => {
        const layer = el.querySelector<SVGRectElement>(`[data-layer="${s.key}"]`)
        if (layer) gsap.set(layer, { attr: { height: 260 * s.fill, y: 330 - 260 * s.fill } })
      })
      gsap.set(el.querySelectorAll('[data-steam]'), { opacity: 0.5 })
      return
    }

    const ctx = gsap.context(() => {
      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: el,
          start: 'top top',
          end: 'bottom bottom',
          scrub: 0.8,
          pin: '[data-pin]',
          pinSpacing: false,
          anticipatePin: 1,
        },
      })

      const innerHeight = CUP.yBottom - CUP.yTop

      STEPS.forEach((step, i) => {
        const at = i * 1.0

        // Hand swings in from the right, tilts to pour, then withdraws.
        tl.fromTo(
          `[data-hand="${step.key}"]`,
          { xPercent: 135, yPercent: -18, rotate: 8, opacity: 0 },
          { xPercent: 0, yPercent: 0, rotate: -22, opacity: 1, duration: 0.35, ease: 'power2.out' },
          at,
        )
          // Stream of ingredient falling into the cup.
          .fromTo(
            `[data-stream="${step.key}"]`,
            { scaleY: 0, opacity: 0, transformOrigin: 'top center' },
            { scaleY: 1, opacity: 1, duration: 0.18, ease: 'power1.out' },
            at + 0.3,
          )
          // Liquid level rises.
          .to(
            `[data-layer="${step.key}"]`,
            {
              attr: { height: innerHeight * step.fill, y: CUP.yBottom - innerHeight * step.fill },
              duration: 0.42,
              ease: 'power1.inOut',
            },
            at + 0.34,
          )
          // Surface ripple as it lands.
          .fromTo(
            `[data-ripple="${step.key}"]`,
            { scaleX: 0.2, opacity: 0.85 },
            { scaleX: 1.5, opacity: 0, duration: 0.4, ease: 'power2.out' },
            at + 0.36,
          )
          .to(`[data-stream="${step.key}"]`, { scaleY: 0, opacity: 0, duration: 0.15 }, at + 0.72)
          .to(
            `[data-hand="${step.key}"]`,
            { xPercent: 135, rotate: 8, opacity: 0, duration: 0.3, ease: 'power2.in' },
            at + 0.74,
          )
          // Caption crossfade.
          .fromTo(
            `[data-caption="${step.key}"]`,
            { opacity: 0, y: 22 },
            { opacity: 1, y: 0, duration: 0.28, ease: 'power2.out' },
            at + 0.15,
          )
          .to(`[data-caption="${step.key}"]`, { opacity: 0, y: -22, duration: 0.25 }, at + 0.8)
      })

      // Steam appears once the water is in and intensifies through the pour.
      tl.fromTo(
        '[data-steam]',
        { opacity: 0 },
        { opacity: 0.55, duration: 0.6, stagger: 0.08 },
        1.4,
      )

      // Final flourish: the finished cup lifts slightly and glows.
      tl.to('[data-cup]', { scale: 1.05, duration: 0.5, ease: 'power2.out' }, STEPS.length - 0.4)
      tl.fromTo(
        '[data-glow]',
        { opacity: 0, scale: 0.7 },
        { opacity: 0.75, scale: 1, duration: 0.5 },
        STEPS.length - 0.4,
      )
    }, el)

    return () => ctx.revert()
  }, [])

  return (
    <div ref={root} className="relative" style={{ height: `${(STEPS.length + 1) * 100}vh` }}>
      <div data-pin className="sticky top-0 flex h-screen items-center overflow-hidden">
        <div className="mx-auto grid w-full max-w-6xl grid-cols-1 items-center gap-8 px-6 lg:grid-cols-2">
          {/* Captions */}
          <div className="relative order-2 h-52 lg:order-1">
            {STEPS.map((s) => (
              <div
                key={s.key}
                data-caption={s.key}
                className="absolute inset-0 flex flex-col justify-center opacity-0"
              >
                <span className="mb-3 inline-flex w-fit items-center gap-2 rounded-full border border-gold/35 bg-gold/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-gold">
                  <span className="h-1.5 w-1.5 rounded-full" style={{ background: s.pourColor }} />
                  Step {STEPS.indexOf(s) + 1} of {STEPS.length}
                </span>
                <h3 className="font-display text-4xl text-latte sm:text-5xl">{s.label}</h3>
                <p className="mt-3 max-w-md text-base leading-relaxed text-latte/55">{s.caption}</p>
              </div>
            ))}
          </div>

          {/* Cup */}
          <div className="relative order-1 flex justify-center lg:order-2">
            <div
              data-glow
              className="pointer-events-none absolute left-1/2 top-1/2 h-72 w-72 -translate-x-1/2 -translate-y-1/2 rounded-full bg-gold/30 opacity-0 blur-[80px]"
            />

            {/* Hands entering from off-screen, one per ingredient */}
            {STEPS.map((s) => (
              <div
                key={s.key}
                data-hand={s.key}
                className="pointer-events-none absolute -right-8 top-2 z-20 opacity-0"
              >
                <PouringHand color={s.pourColor} label={s.label} />
              </div>
            ))}

            <svg
              data-cup
              viewBox="0 0 400 420"
              className="relative z-10 h-[26rem] w-[26rem] drop-shadow-[0_24px_48px_rgba(27,16,10,0.6)]"
              aria-label="A glass cup filling with cappuccino as you scroll"
            >
              <defs>
                <clipPath id="cup-inner">
                  {/* Tapered glass interior — all liquid is clipped to this. */}
                  <path
                    d={`M${CUP.x} ${CUP.yTop}
                        L${CUP.x + CUP.wTop} ${CUP.yTop}
                        L${CUP.x + CUP.wTop - (CUP.wTop - CUP.wBottom) / 2} ${CUP.yBottom}
                        L${CUP.x + (CUP.wTop - CUP.wBottom) / 2} ${CUP.yBottom} Z`}
                  />
                </clipPath>
                <linearGradient id="glass" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#F5E6D3" stopOpacity="0.34" />
                  <stop offset="22%" stopColor="#F5E6D3" stopOpacity="0.10" />
                  <stop offset="78%" stopColor="#F5E6D3" stopOpacity="0.10" />
                  <stop offset="100%" stopColor="#F5E6D3" stopOpacity="0.30" />
                </linearGradient>
                <linearGradient id="saucer" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#E8D5BC" stopOpacity="0.5" />
                  <stop offset="100%" stopColor="#6F4E37" stopOpacity="0.25" />
                </linearGradient>
              </defs>

              {/* Steam */}
              <g clipPath="none">
                {[0, 1, 2].map((i) => (
                  <path
                    key={i}
                    data-steam
                    d={`M${168 + i * 32} ${CUP.yTop - 6}
                        c -14 -26, 14 -40, 0 -66
                        c -12 -22, 10 -34, 2 -50`}
                    stroke="#F5E6D3"
                    strokeWidth="4"
                    strokeLinecap="round"
                    fill="none"
                    opacity="0"
                    className="animate-steam"
                    style={{ animationDelay: `${i * 0.9}s` }}
                  />
                ))}
              </g>

              {/* Falling ingredient streams */}
              {STEPS.map((s) => (
                <rect
                  key={s.key}
                  data-stream={s.key}
                  x={196}
                  y={CUP.yTop - 120}
                  width={8}
                  height={130}
                  rx={4}
                  fill={s.pourColor}
                  opacity={0}
                />
              ))}

              {/* Liquid layers, drawn back-to-front so later ones sit on top */}
              <g clipPath="url(#cup-inner)">
                {STEPS.filter((s) => s.key !== 'cocoa').map((s) => (
                  <rect
                    key={s.key}
                    data-layer={s.key}
                    x={CUP.x - 4}
                    y={CUP.yBottom}
                    width={CUP.wTop + 8}
                    height={0}
                    fill={s.color}
                  />
                ))}
                {/* Cocoa speckles on the foam */}
                <g data-layer="cocoa-dots">
                  {Array.from({ length: 26 }).map((_, i) => (
                    <circle
                      key={i}
                      cx={CUP.x + 16 + ((i * 37) % (CUP.wTop - 30))}
                      cy={CUP.yTop + 18 + ((i * 13) % 16)}
                      r={1.6 + ((i * 7) % 3) * 0.5}
                      fill="#5A3A24"
                      opacity={0.55}
                    />
                  ))}
                </g>
                {STEPS.map((s) => (
                  <ellipse
                    key={s.key}
                    data-ripple={s.key}
                    cx={CUP.x + CUP.wTop / 2}
                    cy={CUP.yTop + 30}
                    rx={40}
                    ry={7}
                    fill="none"
                    stroke="#F5E6D3"
                    strokeWidth="2"
                    opacity={0}
                  />
                ))}
              </g>

              {/* Glass body + highlights */}
              <path
                d={`M${CUP.x} ${CUP.yTop}
                    L${CUP.x + CUP.wTop} ${CUP.yTop}
                    L${CUP.x + CUP.wTop - (CUP.wTop - CUP.wBottom) / 2} ${CUP.yBottom}
                    L${CUP.x + (CUP.wTop - CUP.wBottom) / 2} ${CUP.yBottom} Z`}
                fill="url(#glass)"
                stroke="#F5E6D3"
                strokeOpacity="0.45"
                strokeWidth="2.5"
              />
              <ellipse
                cx={CUP.x + CUP.wTop / 2}
                cy={CUP.yTop}
                rx={CUP.wTop / 2}
                ry={13}
                fill="#F5E6D3"
                fillOpacity="0.10"
                stroke="#F5E6D3"
                strokeOpacity="0.55"
                strokeWidth="2.5"
              />
              <path
                d={`M${CUP.x + 16} ${CUP.yTop + 20} L${CUP.x + 26} ${CUP.yBottom - 26}`}
                stroke="#FBF5EC"
                strokeOpacity="0.28"
                strokeWidth="7"
                strokeLinecap="round"
              />

              {/* Handle */}
              <path
                d={`M${CUP.x + CUP.wTop} ${CUP.yTop + 55}
                    c 52 0, 52 92, 0 92`}
                stroke="#F5E6D3"
                strokeOpacity="0.42"
                strokeWidth="11"
                fill="none"
                strokeLinecap="round"
              />

              {/* Saucer */}
              <ellipse cx={200} cy={CUP.yBottom + 26} rx={128} ry={22} fill="url(#saucer)" />
              <ellipse
                cx={200}
                cy={CUP.yBottom + 22}
                rx={128}
                ry={22}
                fill="none"
                stroke="#E8D5BC"
                strokeOpacity="0.4"
                strokeWidth="2"
              />
            </svg>
          </div>
        </div>

        {/* Scroll affordance */}
        <div className="pointer-events-none absolute bottom-8 left-1/2 -translate-x-1/2 text-center">
          <div className="mx-auto mb-2 h-9 w-5 rounded-full border border-latte/25">
            <div className="mx-auto mt-1.5 h-2 w-1 animate-bounce rounded-full bg-gold" />
          </div>
          <p className="text-[10px] uppercase tracking-[0.3em] text-latte/35">Keep scrolling</p>
        </div>
      </div>
    </div>
  )
}

/** Stylised hand + vessel, tilted to pour. */
function PouringHand({ color, label }: { color: string; label: string }) {
  // An SVG id must not contain spaces — "skin-Hot Water" makes url(#…) fail to
  // resolve and the shape falls back to black.
  const skinId = `skin-${label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`
  return (
    <svg width="200" height="180" viewBox="0 0 200 180" aria-label={`Hand pouring ${label}`}>
      <defs>
        <linearGradient id={skinId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#E8C9A8" />
          <stop offset="100%" stopColor="#C69B72" />
        </linearGradient>
      </defs>
      {/* Forearm reaching in from the right */}
      <path
        d="M196 96 L124 82 c -14 -3, -22 8, -20 20 c 2 12, 12 18, 24 17 l 68 -8 Z"
        fill={`url(#${skinId})`}
        opacity="0.95"
      />
      {/* Fingers wrapped around the vessel */}
      <path
        d="M120 78 c -16 -4, -30 4, -32 18 c -2 14, 8 24, 22 24 c 12 0, 20 -8, 21 -18"
        fill="none"
        stroke={`url(#${skinId})`}
        strokeWidth="15"
        strokeLinecap="round"
      />
      {/* Vessel (jug / grinder), tipped forward */}
      <g transform="rotate(-24 78 84)">
        <path
          d="M44 52 L112 52 L104 116 c -1 8, -8 12, -16 12 L68 128 c -8 0, -15 -4, -16 -12 Z"
          fill="#3B2416"
          stroke="#D9A05B"
          strokeWidth="2.5"
        />
        {/* Contents visible at the lip */}
        <path d="M48 58 L108 58 L106 74 L50 74 Z" fill={color} opacity="0.9" />
        {/* Spout */}
        <path d="M44 56 L18 76 L26 86 L48 68 Z" fill="#3B2416" stroke="#D9A05B" strokeWidth="2.5" />
        <ellipse cx="78" cy="52" rx="34" ry="8" fill="#2A1A12" stroke="#D9A05B" strokeWidth="2.5" />
      </g>
    </svg>
  )
}
