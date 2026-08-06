import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Local dev: forward API calls to the FastAPI server.
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          // framer-motion is used app-wide (toasts, modals, dashboard), so a
          // shared chunk is worth it.
          motion: ['framer-motion'],

          // three.js and GSAP are deliberately NOT listed here.
          //
          // Naming a package in manualChunks makes Vite treat that chunk as
          // part of the initial graph and emit a <link rel="modulepreload">
          // for it in index.html. That preload forced every visitor — phones
          // included — to download ~928 kB of three.js before first paint,
          // even though the device had already decided not to render the 3D
          // scene. Leaving them out lets Rollup derive the chunks from the
          // dynamic import(), so they load only when actually requested.
        },
      },
    },
  },
})
