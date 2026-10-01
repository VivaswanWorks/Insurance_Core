<template>
  <div class="max-w-5xl mx-auto py-8 px-4 space-y-8">
    <header class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-semibold text-gray-900">Insurance Portal</h1>
        <p class="text-gray-600 text-sm" v-if="dashboard?.client">
          Welcome, {{ dashboard.client.full_name }}
        </p>
      </div>
      <div class="flex gap-2">
        <Button @click="$router.push('/policies')">My Policies</Button>
        <Button @click="$router.push('/claims')">My Claims</Button>
        <Button appearance="primary" @click="$router.push('/claims/new')">Intimate Claim</Button>
      </div>
    </header>

    <div v-if="loading" class="text-gray-500">Loading…</div>
    <div v-else-if="error" class="text-red-600 text-sm">{{ error }}</div>
    <template v-else-if="dashboard">
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div class="rounded-lg border bg-white p-4 shadow-sm">
          <div class="text-xs uppercase text-gray-500">Active Policies</div>
          <div class="text-3xl font-semibold">{{ dashboard.stats.active_policies }}</div>
        </div>
        <div class="rounded-lg border bg-white p-4 shadow-sm">
          <div class="text-xs uppercase text-gray-500">Total Policies</div>
          <div class="text-3xl font-semibold">{{ dashboard.stats.total_policies }}</div>
        </div>
        <div class="rounded-lg border bg-white p-4 shadow-sm">
          <div class="text-xs uppercase text-gray-500">Open Claims</div>
          <div class="text-3xl font-semibold">{{ dashboard.stats.open_claims }}</div>
        </div>
      </div>

      <section>
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-lg font-medium">Recent Policies</h2>
          <Button @click="$router.push('/policies')">View all</Button>
        </div>
        <div class="bg-white border rounded-lg divide-y">
          <div
            v-for="p in dashboard.policies"
            :key="p.name"
            class="p-4 flex justify-between items-center hover:bg-gray-50 cursor-pointer"
            @click="$router.push(`/policies/${p.name}`)">
            <div>
              <div class="font-medium">{{ p.policy_number }}</div>
              <div class="text-sm text-gray-500">{{ p.scheme }} · ends {{ p.end_date }}</div>
            </div>
            <span class="text-xs px-2 py-1 rounded-full bg-gray-100">{{ p.status }}</span>
          </div>
          <div v-if="!dashboard.policies.length" class="p-4 text-gray-500 text-sm">No policies yet.</div>
        </div>
      </section>

      <section>
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-lg font-medium">Recent Claims</h2>
          <Button @click="$router.push('/claims')">View all</Button>
        </div>
        <div class="bg-white border rounded-lg divide-y">
          <div
            v-for="c in dashboard.claims"
            :key="c.name"
            class="p-4 flex justify-between items-center hover:bg-gray-50 cursor-pointer"
            @click="$router.push(`/claims/${c.name}`)">
            <div>
              <div class="font-medium">{{ c.claim_number }}</div>
              <div class="text-sm text-gray-500">{{ c.incident_date }} · {{ c.claimed_amount }}</div>
            </div>
            <span class="text-xs px-2 py-1 rounded-full bg-gray-100">{{ c.status }}</span>
          </div>
          <div v-if="!dashboard.claims.length" class="p-4 text-gray-500 text-sm">No claims yet.</div>
        </div>
      </section>
    </template>
  </div>
</template>

<script>
/**
 * Dashboard uses GET (no CSRF) against portal_dashboard which is
 * @frappe.whitelist(methods=["GET", "POST"]).
 * Avoids CSRFTokenError when window.csrf_token is missing / placeholder.
 */
export default {
  name: 'Home',
  data() {
    return {
      dashboard: null,
      loading: true,
      error: null,
    }
  },
  async mounted() {
    await this.loadDashboard()
  },
  methods: {
    async loadDashboard() {
      this.loading = true
      this.error = null
      try {
        const res = await fetch('/api/method/insurance_core.portal.portal_dashboard', {
          method: 'GET',
          credentials: 'same-origin',
          headers: {
            Accept: 'application/json',
            // Harmless if missing; GET does not require CSRF
            'X-Frappe-CSRF-Token': window.csrf_token || '',
          },
        })
        const data = await res.json()
        if (!res.ok || data.exc) {
          let msg = 'Failed to load dashboard'
          try {
            if (data._server_messages) {
              msg = JSON.parse(JSON.parse(data._server_messages)[0]).message || msg
            } else if (data.exception) {
              msg = String(data.exception).split('\n')[0]
            } else if (data.message) {
              msg = typeof data.message === 'string' ? data.message : msg
            }
          } catch (e) {
            /* ignore parse errors */
          }
          this.error = msg
          this.dashboard = null
          return
        }
        this.dashboard = data.message
      } catch (e) {
        this.error = e?.message || String(e)
        this.dashboard = null
      } finally {
        this.loading = false
      }
    },
  },
}
</script>
