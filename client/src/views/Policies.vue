<script setup>
import { ref, watch, onMounted } from 'vue'
import { api, errorMessage } from '../api'
import { money, date, postcode, statusClass } from '../utils/format'

const q = ref('')
const status = ref('all')
const policies = ref([])
const loading = ref(true)
const error = ref(null)

const statuses = [
  { code: 'all', name: 'Any status' }, { code: 'L', name: 'Live' }, { code: 'Q', name: 'Quote' },
  { code: 'X', name: 'Cancelled' }, { code: 'E', name: 'Expired' }, { code: 'D', name: 'Declined' }
]

let timer = null
const load = () => {
  clearTimeout(timer)
  timer = setTimeout(async () => {
    loading.value = true
    try {
      policies.value = await api.getPolicies({ q: q.value.trim(), status: status.value })
      error.value = null
    } catch (err) {
      error.value = errorMessage(err)
    } finally {
      loading.value = false
    }
  }, 250)
}

watch([q, status], load)
onMounted(load)
</script>

<template>
  <h1>Policies</h1>
  <p class="lede">Every policy Heron holds, read through the new API. Open one to adjust it mid-term.</p>

  <div class="filters">
    <div class="grow">
      <label for="q">Policy number, business name or postcode</label>
      <input id="q" v-model="q" autocomplete="off" placeholder="Try Tesselmoor, or HU3">
    </div>
    <div>
      <label for="status">Status</label>
      <select id="status" v-model="status">
        <option v-for="s in statuses" :key="s.code" :value="s.code">{{ s.name }}</option>
      </select>
    </div>
  </div>

  <p v-if="error" class="notice bad" role="alert">{{ error }}</p>
  <div v-else class="sheet">
    <p v-if="!loading && !policies.length" class="quiet">
      No policies match. Clear the search, or start a <router-link to="/quote">new quote</router-link>.
    </p>
    <table v-else class="ruled">
      <thead>
        <tr><th>Policy</th><th>Insured</th><th>Product</th><th>Period</th><th>Status</th><th class="num">Annual premium</th></tr>
      </thead>
      <tbody>
        <tr v-for="p in policies" :key="p.policy_ref">
          <td><router-link :to="`/policies/${p.policy_ref}`">{{ p.policy_ref }}</router-link></td>
          <td>{{ p.insured.name }}<span class="small quiet block">{{ p.trade_name }}, {{ postcode(p.risk.postcode) }}</span></td>
          <td>{{ p.product_name }}</td>
          <td>{{ date(p.inception_date) }} to {{ date(p.expiry_date) }}<span class="small quiet block">Term {{ p.term }}</span></td>
          <td><span class="status" :class="statusClass(p.status)">{{ p.status_name }}</span></td>
          <td class="num">{{ money(p.premium.annual_gross) }}</td>
        </tr>
      </tbody>
    </table>
    <p v-if="policies.length === 50" class="small quiet">Showing the 50 most recently changed. Search to narrow it down.</p>
  </div>
</template>

<style scoped>
.filters { display: flex; gap: var(--s4); margin: var(--s5) 0 var(--s4); align-items: flex-end; }
.grow { flex: 1; }
.block { display: block; }
</style>
