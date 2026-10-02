import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: 'jsdom',
    setupFiles: './src/setupTests.js',
    globals: true,
    pool: 'threads',
    // The App-level tests type into the full page; with many parallel jsdom workers
    // they exceeded the 5s default and failed only under load, never on their own.
    testTimeout: 20000,
  },
})
