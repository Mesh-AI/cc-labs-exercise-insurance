<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'

const report = ref(null)
const loading = ref(true)
const error = ref(null)
const withCoverage = ref(false)
const minPolicies = ref(1000)

const countRows = computed(() => {
  if (!report.value) return []
  const c = report.value.counts
  return [
    { system: 'Heron', what: 'Policies', n: c.policies },
    { system: 'Heron', what: 'Policy terms', n: c.policy_terms },
    { system: 'Heron', what: 'Live policies', n: c.live_policies },
    { system: 'Heron', what: 'Premium transactions', n: c.premium_transactions },
    { system: 'Heron', what: 'Endorsements', n: c.endorsements },
    { system: 'Claims Desk', what: 'Claims', n: c.claims },
    { system: 'Finance Ledger', what: 'Postings', n: c.ledger_postings },
    { system: 'Finance Ledger', what: 'Payments', n: c.payments },
    { system: 'Underwriting Workbench', what: 'Referrals', n: c.referrals },
    { system: 'Underwriting Workbench', what: 'Postcode districts', n: c.accumulation_districts }
  ]
})

const coverageMet = computed(() => (report.value ? report.value.coverage.filter(c => c.met).length : 0))

const load = async () => {
  loading.value = true
  error.value = null
  try {
    report.value = await api.getDataHealth({
      coverage: withCoverage.value,
      minPolicies: withCoverage.value ? Number(minPolicies.value) || 0 : 0
    })
  } catch (err) {
    error.value = 'Could not run the checks. Is the backend running on port 8001?'
  } finally {
    loading.value = false
  }
}

const show = value => (typeof value === 'object' ? JSON.stringify(value) : String(value))

onMounted(load)
</script>

<template>
  <h1>Data health</h1>
  <p class="lede">
    Integrity checks across all four systems, read from the files in <code>server/data</code>.
    The same checks run from the terminal with <code>scripts/check_data.py</code>.
  </p>

  <p v-if="error" class="notice bad" role="alert">{{ error }}</p>
  <p v-else-if="loading" class="quiet">Running the checks.</p>

  <template v-else-if="report">
    <p class="notice" :class="report.error_count ? 'bad' : 'good'" role="status">
      <strong v-if="report.error_count">{{ report.error_count }} integrity errors.</strong>
      <strong v-else>Every integrity check passed.</strong>
      {{ report.warning_count }} warnings from Heron's hand-keyed claim fields.
    </p>

    <section class="block">
      <h2>What each system holds</h2>
      <div class="sheet">
        <table class="ruled">
          <thead><tr><th>System</th><th>Records</th><th class="num">Count</th></tr></thead>
          <tbody>
            <tr v-for="row in countRows" :key="row.system + row.what">
              <td>{{ row.system }}</td><td>{{ row.what }}</td><td class="num">{{ row.n.toLocaleString('en-GB') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="report.errors.length" class="block">
      <h2>Errors</h2>
      <div class="sheet">
        <table class="ruled">
          <thead><tr><th>Check</th><th>What is wrong</th><th class="num">Count</th><th>Examples</th></tr></thead>
          <tbody>
            <tr v-for="e in report.errors" :key="e.check">
              <td><span class="status bad">{{ e.check }}</span></td><td>{{ e.title }}</td>
              <td class="num">{{ e.count }}</td><td class="small">{{ e.examples.join('; ') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="block">
      <h2>Warnings</h2>
      <p>
        Heron stores two claim fields that branch staff copy across from the Claims Desk by hand.
        These are the policies where the copy is out of date. They are the case for the modern journey.
      </p>
      <div class="sheet">
        <p v-if="!report.warnings.length" class="quiet">None.</p>
        <table v-else class="ruled">
          <thead><tr><th>Check</th><th>What has drifted</th><th class="num">Policies</th><th>Examples</th></tr></thead>
          <tbody>
            <tr v-for="w in report.warnings" :key="w.check">
              <td><span class="status warn">{{ w.check }}</span></td><td>{{ w.title }}</td>
              <td class="num">{{ w.count }}</td><td class="small">{{ w.examples.join('; ') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="block">
      <h2>Coverage targets for a generated book</h2>
      <p>
        The sample extract is too small to test a new journey properly. Once your generator has written
        a bigger book, check that it covers the cases that matter.
      </p>
      <div class="controls">
        <div>
          <label for="min-policies">Minimum policies</label>
          <input id="min-policies" v-model="minPolicies" type="number" min="1" step="100">
        </div>
        <button @click="withCoverage = true; load()">Check coverage</button>
      </div>
      <div v-if="report.coverage.length" class="sheet">
        <p><strong>{{ coverageMet }} of {{ report.coverage.length }} targets met.</strong></p>
        <table class="ruled">
          <thead><tr><th>Target</th><th>Result</th><th>What it needs</th><th>Actual</th></tr></thead>
          <tbody>
            <tr v-for="c in report.coverage" :key="c.target">
              <td>{{ c.target }}</td>
              <td><span class="status" :class="c.met ? 'good' : 'bad'">{{ c.met ? 'Met' : 'Not met' }}</span></td>
              <td>{{ c.title }}</td><td class="small">{{ show(c.actual) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </template>
</template>

<style scoped>
.block { margin-top: var(--s6); }
code { background: var(--larkspur-wash); padding: 0 var(--s1); border-radius: 2px; }
.controls { display: flex; gap: var(--s4); align-items: flex-end; margin-bottom: var(--s4); }
.controls input { width: 9rem; }
</style>
