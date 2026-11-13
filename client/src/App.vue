<script setup>
import { ref, onMounted } from 'vue'
import { api, LEGACY_URL } from './api'

const labDate = ref('')
const backendDown = ref(false)

onMounted(async () => {
  try {
    const health = await api.getHealth()
    labDate.value = new Date(health.lab_date + 'T00:00:00').toLocaleDateString('en-GB', {
      day: 'numeric', month: 'long', year: 'numeric'
    })
  } catch (err) {
    backendDown.value = true
  }
})
</script>

<template>
  <div class="shell">
    <header class="rail">
      <router-link to="/" class="wordmark">Larkspur <span>&amp;</span> Dene</router-link>
      <p class="strap">Policy modernisation workbench</p>
      <nav aria-label="Main">
        <router-link to="/">Workbench</router-link>
        <router-link to="/quote">New quote</router-link>
        <router-link to="/policies">Policies</router-link>
        <router-link to="/data">Data health</router-link>
      </nav>
      <p class="rail-heading">The estate</p>
      <nav aria-label="Systems">
        <a :href="LEGACY_URL" target="_blank" rel="noopener">Heron (legacy screens)</a>
        <a href="/api/systems/underwriting/docs" target="_blank" rel="noopener">Underwriting API</a>
        <a href="/api/systems/claims/docs" target="_blank" rel="noopener">Claims API</a>
        <a href="/api/systems/finance/docs" target="_blank" rel="noopener">Finance API</a>
      </nav>
      <p v-if="labDate" class="clock">Lab date <strong>{{ labDate }}</strong><br>Synthetic data only</p>
    </header>
    <main>
      <p v-if="backendDown" class="notice bad" role="alert">
        The backend is not answering on port 8001. Run <code>./scripts/start.sh</code> from the project root, then reload.
      </p>
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.shell { display: grid; grid-template-columns: var(--rail) minmax(0, 1fr); min-height: 100vh; }
.rail { background: var(--ink); color: #dfe3ee; padding: var(--s5) var(--s4); }
.wordmark { font-family: var(--serif); font-size: var(--step-2); color: #fff; text-decoration: none; line-height: 1.1; display: block; }
.wordmark span { color: #a9adf0; }
.strap { font-size: var(--step--1); color: #aab2c8; margin: var(--s2) 0 var(--s5); }
nav { display: flex; flex-direction: column; gap: 2px; }
nav a { color: #dfe3ee; text-decoration: none; padding: var(--s2) var(--s3); border-radius: var(--radius); border-left: 3px solid transparent; }
nav a:hover { background: rgba(255, 255, 255, 0.08); }
nav a.router-link-active:not([href$='#/']), nav a.router-link-exact-active { border-left-color: #a9adf0; background: rgba(255, 255, 255, 0.1); color: #fff; font-weight: 600; }
nav a:focus-visible { outline-color: #fff; }
.rail-heading { font-size: var(--step--1); color: #aab2c8; margin: var(--s5) 0 var(--s2) var(--s3); }
.clock { font-size: var(--step--1); color: #aab2c8; margin: var(--s6) 0 0 var(--s3); }
.clock strong { color: #fff; }
main { padding: var(--s6) var(--s6) var(--s7); max-width: 72rem; }
code { background: rgba(0, 0, 0, 0.06); padding: 0 var(--s1); border-radius: 2px; }

@media (max-width: 800px) {
  .shell { grid-template-columns: 1fr; }
  .rail { padding: var(--s4); }
  .strap { margin-bottom: var(--s3); }
  nav { flex-direction: row; flex-wrap: wrap; }
  .rail-heading, .clock { display: none; }
  main { padding: var(--s5) var(--s4) var(--s6); }
}
</style>
