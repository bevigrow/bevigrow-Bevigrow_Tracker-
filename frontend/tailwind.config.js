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
      keyframes: {
        steam: {
          '0%': { transform: 'translateY(0) scaleX(1)', opacity: '0' },
          '15%': { opacity: '0.55' },
          '100%': { transform: 'translateY(-42px) scaleX(1.7)', opacity: '0' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        ripple: {
          '0%': { transform: 'scale(0)', opacity: '0.45' },
          '100%': { transform: 'scale(3.2)', opacity: '0' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-480px 0' },
          '100%': { backgroundPosition: '480px 0' },
        },
        pourfill: {
          '0%': { height: '0%' },
          '100%': { height: '100%' },
        },
        /* Replacements for the framer-motion entrances. CSS does these on the
           compositor without 122 kB of JavaScript in the critical path. */
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
        steam: 'steam 3.6s ease-out infinite',
        float: 'float 6s ease-in-out infinite',
        ripple: 'ripple 700ms ease-out forwards',
        shimmer: 'shimmer 1.6s linear infinite',
      },
    },
  },
  plugins: [],
}
