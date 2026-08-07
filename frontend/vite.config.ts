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
      // No manualChunks. Naming a package here makes Vite treat that chunk as
      // part of the initial graph and emit a <link rel="modulepreload"> for
      // it, which pulls the bytes down before first paint whether or not the
      // page needs them. Letting Rollup derive chunks from the real imports
      // keeps the critical path to what the route actually uses.
    },
  },
})
