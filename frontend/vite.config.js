import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import fs from 'fs'

function loadProxy() {
  const configPath = path.resolve(__dirname, '../../../sites/common_site_config.json')
  if (!fs.existsSync(configPath)) {
    return {}
  }
  try {
    const { getProxyOptions } = require('frappe-ui/src/utils/vite-dev-server')
    const { webserver_port } = JSON.parse(fs.readFileSync(configPath, 'utf8'))
    return getProxyOptions({ port: webserver_port })
  } catch (e) {
    return {}
  }
}

// Frappe serves apps/<app>/<python_pkg>/public/** as /assets/<app>/**
// Repo layout: apps/insurance_core/frontend → apps/insurance_core/insurance_core/public/frontend
const outDir = path.resolve(__dirname, '../insurance_core/public/frontend')

export default defineConfig(({ command }) => ({
  plugins: [vue()],
  // Production asset URL prefix (must match www/insurance_core.html)
  base: command === 'build' ? '/assets/insurance_core/frontend/' : '/',
  server: {
    host: true,
    port: 8080,
    allowedHosts: ['.monkeycode-ai.live'],
    proxy: loadProxy(),
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  build: {
    outDir,
    emptyOutDir: true,
    target: 'es2015',
    // One stylesheet only — avoids multiple CSS chunks all named index.css
    // (that overwrote the full Tailwind build with the tiny TipTap sheet).
    cssCodeSplit: false,
    rollupOptions: {
      input: path.resolve(__dirname, 'index.html'),
      output: {
        entryFileNames: 'index.js',
        chunkFileNames: '[name]-[hash].js',
        assetFileNames: (assetInfo) => {
          const name = assetInfo.name || ''
          if (name.endsWith('.css')) {
            return 'index.css'
          }
          // Fonts and other assets keep stable names
          return '[name][extname]'
        },
      },
    },
  },
  optimizeDeps: {
    include: ['frappe-ui > feather-icons', 'showdown', 'engine.io-client'],
  },
}))
