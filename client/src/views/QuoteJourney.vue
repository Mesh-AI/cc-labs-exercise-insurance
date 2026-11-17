<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { api, errorMessage } from '../api'
import { money, date, postcode as showPostcode } from '../utils/format'
import PremiumSchedule from '../components/PremiumSchedule.vue'
import DecisionBanner from '../components/DecisionBanner.vue'

const lookups = ref(null)
const loadError = ref(null)

const form = reactive({
  user: 'CLERK1',
  broker_code: '',
  customer: 'new',
  insured: { name: '', address: '', town: '' },
  insured_ref: null,
  insured_label: '',
  inception_date: '',
  risk: {
    product: 'CP', trade_code: 'RETL', postcode: '', construction: 1,
    sum_insured_buildings: 0, sum_insured_contents: 0, sum_insured_bi: 0,
    turnover: 0, employees: 0, voluntary_excess: 250, claims_count_3y: 0
  }
})

const search = ref('')
const matches = ref([])
const priced = ref(null)
const pricing = ref(false)
const priceError = ref(null)
const saved = ref(null)
const bound = ref(null)
const busy = ref(false)
const actionError = ref(null)

const isProperty = computed(() => form.risk.product === 'CP')

// For an existing customer the backend prices on the Claims Desk's count, not the typed one.
const isExisting = computed(() => form.customer === 'existing' && !!form.insured_ref)
const claimsFromDesk = computed(() => isExisting.value && priced.value?.claims_count?.source === 'claims_desk')
const claimsDeskDown = computed(() => isExisting.value && !!priced.value?.claims_count?.claims_desk_unavailable)

const canPrice = computed(() => {
  const r = form.risk
  if (r.postcode.replace(/\s/g, '').length < 5) return false
  return isProperty.value
    ? r.sum_insured_buildings + r.sum_insured_contents > 0
    : r.employees > 0 && r.turnover > 0
})

const canSave = computed(() =>
  priced.value && !priceError.value && form.broker_code && form.inception_date &&
  (form.customer === 'existing' ? form.insured_ref : form.insured.name.trim()) &&
  priced.value.decision !== 'decline'
)

const riskPayload = () => ({ ...form.risk, postcode: form.risk.postcode.toUpperCase() })

let timer = null
const reprice = () => {
  clearTimeout(timer)
  if (saved.value) return
  if (!canPrice.value) { priced.value = null; priceError.value = null; return }
  pricing.value = true
  timer = setTimeout(async () => {
    try {
      priced.value = await api.priceQuote({
        risk: riskPayload(),
        broker_code: form.broker_code || null,
        insured_ref: form.customer === 'existing' ? form.insured_ref : null
      })
      priceError.value = null
    } catch (err) {
      priceError.value = errorMessage(err)
    } finally {
      pricing.value = false
    }
  }, 350)
}

watch(() => [form.risk, form.broker_code, form.insured_ref, form.customer], reprice, { deep: true })

watch(search, async q => {
  matches.value = q.trim().length >= 2 ? await api.findInsureds(q.trim()) : []
})

const chooseInsured = m => {
  form.insured_ref = m.ref
  form.insured_label = `${m.name}, ${m.town} ${showPostcode(m.postcode)}`
  form.risk.trade_code = m.trade_code
  if (!form.risk.postcode) form.risk.postcode = showPostcode(m.postcode)
  search.value = ''
  matches.value = []
}

const clearInsured = () => { form.insured_ref = null; form.insured_label = '' }

const saveQuote = async () => {
  busy.value = true
  actionError.value = null
  try {
    saved.value = await api.createQuote({
      risk: riskPayload(),
      broker_code: form.broker_code,
      inception_date: form.inception_date,
      insured: form.customer === 'new' ? form.insured : null,
      insured_ref: form.customer === 'existing' ? form.insured_ref : null,
      user: form.user
    })
    priced.value = { ...priced.value, ...saved.value }
  } catch (err) {
    actionError.value = errorMessage(err)
  } finally {
    busy.value = false
  }
}

const bindQuote = async () => {
  busy.value = true
  actionError.value = null
  try {
    bound.value = await api.bindQuote(saved.value.policy.policy_ref, { user: form.user })
  } catch (err) {
    actionError.value = errorMessage(err)
  } finally {
    busy.value = false
  }
}

const startAgain = () => {
  saved.value = null
  bound.value = null
  priced.value = null
  actionError.value = null
  form.insured = { name: '', address: '', town: '' }
  clearInsured()
  reprice()
}

onMounted(async () => {
  try {
    lookups.value = await api.getLookups()
    const start = new Date(lookups.value.lab_date + 'T00:00:00')
    start.setDate(start.getDate() + 14)
    form.inception_date = start.toISOString().slice(0, 10)
  } catch (err) {
    loadError.value = errorMessage(err)
  }
})
</script>

<template>
  <h1>New business quote</h1>
  <p class="lede">
    The same answer Heron's NBQTE screen gives, without the re-keying. The price updates as you type.
  </p>
  <p v-if="loadError" class="notice bad" role="alert">{{ loadError }}</p>

  <div v-if="lookups" class="journey">
    <form class="sheet" @submit.prevent>
      <fieldset :disabled="!!saved">
        <legend>Who it is for</legend>
        <div class="row">
          <div>
            <label for="broker">Broker</label>
            <select id="broker" v-model="form.broker_code">
              <option value="" disabled>Choose a broker</option>
              <option v-for="b in lookups.brokers" :key="b.code" :value="b.code">{{ b.name }} ({{ b.code }})</option>
            </select>
          </div>
          <div>
            <label for="user">Signed in as</label>
            <select id="user" v-model="form.user">
              <option value="CLERK1">Branch clerk (CLERK1)</option>
              <option value="UWMGR1">Underwriting manager (UWMGR1)</option>
            </select>
          </div>
        </div>
        <div class="choice" role="radiogroup" aria-label="Customer">
          <label><input v-model="form.customer" type="radio" value="new"> New customer</label>
          <label><input v-model="form.customer" type="radio" value="existing"> Existing customer</label>
        </div>
        <template v-if="form.customer === 'new'">
          <label for="name">Business name</label>
          <input id="name" v-model="form.insured.name" autocomplete="off">
          <div class="row">
            <div><label for="address">Address</label><input id="address" v-model="form.insured.address" autocomplete="off"></div>
            <div><label for="town">Town</label><input id="town" v-model="form.insured.town" autocomplete="off"></div>
          </div>
        </template>
        <template v-else>
          <div v-if="form.insured_ref" class="chosen">
            <span><strong>{{ form.insured_label }}</strong> <span class="quiet">(insured {{ form.insured_ref }})</span></span>
            <button type="button" class="secondary" @click="clearInsured">Change</button>
          </div>
          <template v-else>
            <label for="search">Find the customer by name</label>
            <input id="search" v-model="search" autocomplete="off" placeholder="Try Varrowstone">
            <ul v-if="matches.length" class="matches">
              <li v-for="m in matches" :key="m.ref">
                <button type="button" class="secondary" @click="chooseInsured(m)">{{ m.name }}, {{ m.town }}</button>
              </li>
            </ul>
          </template>
        </template>
      </fieldset>

      <fieldset :disabled="!!saved">
        <legend>What is being insured</legend>
        <div class="choice" role="radiogroup" aria-label="Product">
          <label v-for="p in lookups.products" :key="p.code">
            <input v-model="form.risk.product" type="radio" :value="p.code"> {{ p.name }}
          </label>
        </div>
        <div class="row">
          <div>
            <label for="trade">Trade</label>
            <select id="trade" v-model="form.risk.trade_code">
              <option v-for="t in lookups.trades" :key="t.code" :value="t.code">{{ t.name }}</option>
            </select>
          </div>
          <div>
            <label for="postcode">Risk postcode</label>
            <input id="postcode" v-model="form.risk.postcode" autocomplete="off" placeholder="M4 3KV">
          </div>
        </div>
        <template v-if="isProperty">
          <div class="row">
            <div>
              <label for="construction">Construction</label>
              <select id="construction" v-model.number="form.risk.construction">
                <option v-for="c in lookups.constructions" :key="c.code" :value="c.code">{{ c.name }}</option>
              </select>
            </div>
            <div>
              <label for="excess">Voluntary excess</label>
              <select id="excess" v-model.number="form.risk.voluntary_excess">
                <option v-for="x in lookups.voluntary_excesses" :key="x" :value="x">£{{ x.toLocaleString('en-GB') }}</option>
              </select>
            </div>
          </div>
          <div class="row three">
            <div><label for="bld">Buildings sum insured (£)</label><input id="bld" v-model.number="form.risk.sum_insured_buildings" type="number" min="0" step="5000"></div>
            <div><label for="cnt">Contents sum insured (£)</label><input id="cnt" v-model.number="form.risk.sum_insured_contents" type="number" min="0" step="1000"></div>
            <div><label for="bi">Business interruption (£)</label><input id="bi" v-model.number="form.risk.sum_insured_bi" type="number" min="0" step="5000"></div>
          </div>
        </template>
        <div v-else class="row">
          <div><label for="turnover">Annual turnover (£)</label><input id="turnover" v-model.number="form.risk.turnover" type="number" min="0" step="5000"></div>
          <div><label for="employees">Employees</label><input id="employees" v-model.number="form.risk.employees" type="number" min="0"></div>
        </div>
        <div class="row">
          <div>
            <label for="inception">Cover starts</label>
            <input id="inception" v-model="form.inception_date" type="date">
          </div>
          <div>
            <label for="claims">Claims in the last three years</label>
            <template v-if="claimsFromDesk">
              <input id="claims" :value="priced.claims_count.value" type="number" readonly>
              <span class="small quiet">From Claims Desk</span>
            </template>
            <input v-else id="claims" v-model.number="form.risk.claims_count_3y" type="number" min="0" max="9">
            <p v-if="claimsDeskDown" class="notice warn small" role="status">{{ priced.claims_count.message }}</p>
          </div>
        </div>
      </fieldset>
    </form>

    <aside>
      <PremiumSchedule :price="priced ? priced.price : null" :stale="pricing" />
      <p v-if="priceError" class="notice bad" role="alert">{{ priceError }}</p>
      <DecisionBanner v-else-if="priced && !bound" :decision="priced.decision" :reasons="priced.decision_reasons" />


      <p v-if="actionError" class="notice bad" role="alert">{{ actionError }}</p>

      <div v-if="!saved" class="actions">
        <button :disabled="!canSave || busy" @click="saveQuote">Save quote</button>
        <span v-if="priced && !canSave && priced.decision !== 'decline'" class="small quiet">Add the broker and the customer to save.</span>
      </div>

      <div v-else-if="!bound" class="sheet side">
        <h3>Quote {{ saved.policy.policy_ref }} saved</h3>
        <p>For {{ saved.policy.insured.name }}, starting {{ date(saved.policy.inception_date) }}. It is in Heron now and valid for 30 days.</p>
        <div class="actions">
          <button :disabled="busy" @click="bindQuote">Bind policy</button>
          <button class="secondary" :disabled="busy" @click="startAgain">Start another quote</button>
        </div>
      </div>

      <div v-else class="sheet side">
        <h3>Policy {{ bound.policy.policy_ref }} is live</h3>
        <p>
          Heron wrote transaction {{ bound.transaction.transaction_ref }} for
          {{ money(bound.transaction.gross_premium) }} plus {{ money(bound.transaction.ipt) }} tax.
        </p>
        <p v-if="bound.finance?.posted">Posted to the Finance Ledger as <strong>{{ bound.finance.posting_ref }}</strong>.</p>
        <p v-else-if="bound.finance" class="notice warn small" role="status">{{ bound.finance.message }}</p>
        <div class="actions">
          <router-link class="button" :to="`/policies/${bound.policy.policy_ref}`">Open the policy</router-link>
          <button class="secondary" @click="startAgain">Start another quote</button>
        </div>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.journey { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(19rem, 1fr); gap: var(--s5); align-items: start; margin-top: var(--s5); }
aside { position: sticky; top: var(--s4); display: grid; gap: var(--s4); }
aside > * { margin: 0; }
fieldset { border: 0; padding: 0; margin: 0 0 var(--s5); }
fieldset:last-child { margin-bottom: 0; }
legend { font-family: var(--serif); font-size: var(--step-1); font-weight: 600; padding: 0; margin-bottom: var(--s3); }
.row { display: grid; grid-template-columns: 1fr 1fr; gap: var(--s4); margin-bottom: var(--s4); }
.row.three { grid-template-columns: 1fr 1fr 1fr; }
fieldset > label, fieldset > input { margin-bottom: var(--s1); }
fieldset > input { margin-bottom: var(--s4); }
.choice { display: flex; gap: var(--s5); margin-bottom: var(--s4); }
.choice label { display: inline-flex; align-items: center; gap: var(--s2); font-weight: 400; font-size: var(--step-0); margin: 0; }
.choice input { width: auto; }
.chosen { display: flex; justify-content: space-between; align-items: center; gap: var(--s3); padding: var(--s3); background: var(--larkspur-wash); border-radius: var(--radius); }
.matches { list-style: none; margin: var(--s2) 0 0; padding: 0; display: grid; gap: var(--s1); }
.matches button { width: 100%; text-align: left; font-weight: 400; border-color: var(--rule); color: var(--ink); }
input[readonly] { background: var(--larkspur-wash); cursor: default; }
.from-system { margin: 0; padding: var(--s2) 0; }
.from-system span { display: block; }
.side h3 { margin-bottom: var(--s3); }
.side p:last-child { margin-bottom: 0; }
.actions { display: flex; gap: var(--s3); align-items: center; flex-wrap: wrap; }

@media (max-width: 1000px) {
  .journey { grid-template-columns: 1fr; }
  aside { position: static; }
  .row, .row.three { grid-template-columns: 1fr; }
}
</style>
