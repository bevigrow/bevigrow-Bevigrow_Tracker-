/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        espresso: '#3B2416',
        darkroast: '#2A1A12',
        caramel: '#C68B59',
        latte: '#F5E6D3',
        mocha: '#6F4E37',
        gold: '#D9A05B',
        // Derived shades for depth
        bean: '#1B100A',
        crema: '#E8D5BC',
        foam: '#FBF5EC',
      },
      fontFamily: {
        display: ['"Playfair Display"', '"Cormorant Garamond"', 'Georgia', 'serif'],
        body: ['Inter', 'Poppins', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        cup: '0 20px 48px -18px rgba(27, 16, 10, 0.55)',
        lift: '0 12px 32px -12px rgba(27, 16, 10, 0.4)',
        glow: '0 0 0 1px rgba(217, 160, 91, 0.35), 0 8px 28px -10px rgba(217, 160, 91, 0.4)',
      },
      backgroundImage: {
        'roast-gradient': 'linear-gradient(135deg, #2A1A12 0%, #3B2416 45%, #6F4E37 100%)',
        'gold-gradient': 'linear-gradient(120deg, #D9A05B 0%, #C68B59 55%, #A5713F 100%)',
        'crema-gradient': 'linear-gradient(180deg, #F5E6D3 0%, #E8D5BC 100%)',
      },
      /*
        Every animation here runs once and stops.

        There is no `infinite` in this file any more, and that is the rule
        worth keeping. The three that were removed — steam, float, shimmer —
        never finished, so a page that looked completely still was repainting
        forever. On WebKit two floating emoji on the trade dashboard cost
        393 ms per frame while idle; Chromium composited the same markup for
        free, which is why it only ever showed up on iPhones.

        Entrances are safe because they end. If a perpetual animation is ever
        added back, animate only `opacity` and `transform` — those the
        compositor can run without repainting. `background-position` (what
        shimmer used) and `filter` (what steam used, via blur) both force a
        repaint every single frame.
      */
      keyframes: {
        fadeIn: {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        fadeInUp: {
          from: { opacity: '0', transform: 'translateY(24px)' },
          to: { opacity: '1', transform: 'none' },
        },
        fadeInUpSm: {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to: { opacity: '1', transform: 'none' },
        },
        scaleIn: {
          from: { opacity: '0', transform: 'scale(.97) translateY(16px)' },
          to: { opacity: '1', transform: 'none' },
        },
        slideInRight: {
          from: { opacity: '0', transform: 'translateX(60px) scale(.94)' },
          to: { opacity: '1', transform: 'none' },
        },
      },
      animation: {
        'fade-in': 'fadeIn .4s ease-out both',
        'fade-in-up': 'fadeInUp .6s cubic-bezier(.16,1,.3,1) both',
        'fade-in-up-sm': 'fadeInUpSm .4s ease-out both',
        'scale-in': 'scaleIn .28s cubic-bezier(.16,1,.3,1) both',
        'slide-in-right': 'slideInRight .32s cubic-bezier(.16,1,.3,1) both',
      },
    },
  },
  plugins: [],
}
