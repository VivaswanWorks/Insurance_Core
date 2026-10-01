import './index.css'

import { createApp } from 'vue'
import router from './router'
import App from './App.vue'

import { Button, setConfig, frappeRequest, resourcesPlugin } from 'frappe-ui'

/**
 * Ensure window.csrf_token is a real token before any resource fetch.
 *
 * Production page (www/insurance_core.html) injects it via Jinja.
 * Fallback chain:
 *   1. existing window.csrf_token / frappe.boot.csrf_token (if not placeholder)
 *   2. csrf_token cookie
 *   3. GET /api/method/frappe.sessions.get_csrf_token
 *   4. GET /api/method/frappe.auth.get_logged_user (boot often includes token)
 *
 * Note: no top-level await — Vite/esbuild target is es2015.
 */
function isBadToken(t) {
  return (
    !t ||
    t === '{{ csrf_token }}' ||
    t === 'None' ||
    t === 'null' ||
    t === 'undefined' ||
    t === 'null' ||
    String(t).includes('csrf_token')
  )
}

function applyToken(token) {
  if (isBadToken(token)) return false
  window.csrf_token = token
  try {
    window.frappe = window.frappe || {}
    window.frappe.csrf_token = token
    window.frappe.boot = window.frappe.boot || {}
    window.frappe.boot.csrf_token = token
  } catch (e) {
    /* ignore */
  }
  // Keep cookie in sync for libraries that read it
  try {
    document.cookie = `csrf_token=${encodeURIComponent(token)}; path=/; SameSite=Lax`
  } catch (e) {
    /* ignore */
  }
  return true
}

async function ensureCsrfToken() {
  // 1. Window / boot
  if (applyToken(window.csrf_token)) return
  try {
    if (window.frappe?.boot?.csrf_token && applyToken(window.frappe.boot.csrf_token)) return
    if (window.frappe?.csrf_token && applyToken(window.frappe.csrf_token)) return
  } catch (e) {
    /* ignore */
  }

  // 2. Cookie
  try {
    const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
    if (m && m[1] && applyToken(decodeURIComponent(m[1]))) return
  } catch (e) {
    /* ignore */
  }

  // 3. Explicit session API
  try {
    const res = await fetch('/api/method/frappe.sessions.get_csrf_token', {
      method: 'GET',
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
    if (res.ok) {
      const data = await res.json()
      const token = data?.message
      if (applyToken(token)) return
    }
  } catch (e) {
    console.warn('[insurance_core] CSRF refresh (get_csrf_token) failed', e)
  }

  // 4. Last resort: any API that echoes session (logged-in user)
  try {
    const res = await fetch('/api/method/frappe.auth.get_logged_user', {
      method: 'GET',
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
    // Re-check cookie after a successful session call
    if (res.ok) {
      const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
      if (m && m[1] && applyToken(decodeURIComponent(m[1]))) return
    }
  } catch (e) {
    console.warn('[insurance_core] CSRF refresh (get_logged_user) failed', e)
  }

  console.warn(
    '[insurance_core] No CSRF token available. Portal API POSTs will fail. ' +
      'Serve the SPA via www/insurance_core.html (Jinja) and ensure you are logged in.',
  )
}

/**
 * Wrap frappeRequest so every call carries the latest token.
 * frappe-ui always POSTs to /api/method/... which requires X-Frappe-CSRF-Token.
 */
async function csrfAwareRequest(options) {
  if (isBadToken(window.csrf_token)) {
    await ensureCsrfToken()
  }
  const opts = options || {}
  const headers = Object.assign({}, opts.headers || {}, {
    'X-Frappe-CSRF-Token': window.csrf_token || '',
  })
  return frappeRequest(Object.assign({}, opts, { headers }))
}

function mountApp() {
  const app = createApp(App)

  setConfig('resourceFetcher', csrfAwareRequest)

  app.use(router)
  app.use(resourcesPlugin)

  app.component('Button', Button)
  app.mount('#app')
}

// Async bootstrap without top-level await (es2015 target)
ensureCsrfToken()
  .catch((e) => console.warn('[insurance_core] CSRF bootstrap error', e))
  .finally(() => mountApp())
