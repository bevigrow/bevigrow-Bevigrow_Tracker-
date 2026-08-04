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
          // Three.js and GSAP are only reachable from the lazy-loaded landing
          // page, so keeping them in their own chunks means authenticated
          // routes never download them.
          three: ['three', '@react-three/fiber', '@react-three/drei'],
          gsap: ['gsap'],
          // framer-motion is used app-wide (toasts, modals, dashboard).
          motion: ['framer-motion'],
        },
      },
    },
  },
})
