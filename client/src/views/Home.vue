<script setup>
import { ref, onMounted } from 'vue'
import { api, LEGACY_URL } from '../api'
import EstateMap from '../components/EstateMap.vue'

const systems = ref([])
const error = ref(null)

const built = [
  { name: 'New business quote and bind', legacy: 'nbqte', screen: 'NBQTE', modern: '/quote' },
  { name: 'Mid-term adjustment', legacy: 'polenq', screen: 'MTAENT', modern: '/policies' }
]

// The five change cards. Full text in docs/cards. Each is one block's work.
const cards = [
  { n: 1, title: 'Claim count from the claims system', system: 'Claims Desk', size: 'Small' },
  { n: 2, title: 'Premium to finance at bind', system: 'Finance Ledger', size: 'Small' },
  { n: 3, title: 'Technical price check', system: 'Underwriting Workbench', size: 'Medium' },
  { n: 4, title: 'Credit hold warning', system: 'Finance Ledger', size: 'Medium' },
  { n: 5, title: 'Claims history on the policy', system: 'Claims Desk', size: 'Medium' }
]

onMounted(async () => {
  try {
    systems.value = await api.getSystemsStatus()
  } catch (err) {
    error.value = 'Could not load the systems. Is the backend running on port 8001?'
  }
})
</script>

<template>
  <section>
    <h1>A modern front end that still talks to nothing</h1>
    <p class="lede">
      Heron has priced every commercial policy at Larkspur &amp; Dene since 2004. A new front end and API now
      sit on top of it, giving exactly Heron's answers. Underwriting, claims and finance each run their own
      system, and people still carry the data between them. Each change card connects one of them.
    </p>
  </section>

  <section class="block">
    <h2>The estate today</h2>
    <p v-if="error" class="notice bad" role="alert">{{ error }}</p>
    <div class="sheet">
      <EstateMap :systems="systems" />
    </div>
  </section>

  <section class="block">
    <h2>Already built</h2>
    <div class="sheet">
      <table class="ruled">
        <thead><tr><th>Journey</th><th>In Heron</th><th>New version</th></tr></thead>
        <tbody>
          <tr v-for="j in built" :key="j.screen">
            <td><strong>{{ j.name }}</strong></td>
            <td><a :href="LEGACY_URL + j.legacy" target="_blank" rel="noopener">Screen {{ j.screen }}</a></td>
            <td><router-link :to="j.modern" class="status good">Open</router-link></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <section class="block">
    <h2>Change cards</h2>
    <p>
      Pick one card per hands-on block and take it from intent to spec to working code with your harness.
      Cards 1 and 2 are the smallest. The full cards are in <code>docs/cards</code>.
    </p>
    <div class="sheet">
      <table class="ruled">
        <thead><tr><th>Card</th><th>Change</th><th>Connects to</th><th>Size</th></tr></thead>
        <tbody>
          <tr v-for="c in cards" :key="c.n">
            <td>{{ c.n }}</td><td><strong>{{ c.title }}</strong></td><td>{{ c.system }}</td><td class="quiet">{{ c.size }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.block { margin-top: var(--s6); }
code { background: var(--larkspur-wash); padding: 0 var(--s1); border-radius: 2px; }
table.ruled td:first-child { white-space: nowrap; }
</style>
