<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api, errorMessage } from '../api'
import { money, pounds, date, postcode, statusClass } from '../utils/format'

const route = useRoute()
const policy = ref(null)
const lookups = ref(null)
const error = ref(null)

const adjust = reactive({ open: false, effective_date: '', user: 'CLERK1', risk: {} })
const preview = ref(null)
const applied = ref(null)
const adjustError = ref(null)
const busy = ref(false)

const isProperty = computed(() => policy.value && policy.value.product === 'CP')
const isLive = computed(() => policy.value && policy.value.status === 'L')

const changes = computed(() => {
  const out = {}
  if (!policy.value) return out
  for (const [k, v] of Object.entries(adjust.risk)) {
    const now = k === 'postcode' ? String(v).replace(/\s/g, '').toUpperCase() : v
    if (now !== policy.value.risk[k] && v !== '' && v !== null) out[k] = now
  }
  return out
})
const hasChanges = computed(() => Object.keys(changes.value).length > 0)

const load = async () => {
  error.value = null
  try {
    policy.value = await api.getPolicy(route.params.ref)
    if (!lookups.value) lookups.value = await api.getLookups()
    const today = lookups.value.lab_date
    adjust.effective_date = today >= policy.value.inception_date && today < policy.value.expiry_date
      ? today : policy.value.inception_date
    adjust.risk = { ...policy.value.risk, postcode: postcode(policy.value.risk.postcode) }
    delete adjust.risk.product
    delete adjust.risk.claims_count_3y
  } catch (err) {
    error.value = errorMessage(err)
  }
}

let timer = null
watch(() => [adjust.risk, adjust.effective_date, adjust.user], () => {
  clearTimeout(timer)
  applied.value = null
  if (!adjust.open || !hasChanges.value) { preview.value = null; adjustError.value = null; return }
  timer = setTimeout(async () => {
    try {
      preview.value = await api.previewAdjustment(policy.value.policy_ref, {
        effective_date: adjust.effective_date, changes: changes.value, user: adjust.user
      })
      adjustError.value = null
    } catch (err) {
      preview.value = null
      adjustError.value = errorMessage(err)
    }
  }, 350)
}, { deep: true })

const apply = async () => {
  busy.value = true
  try {
    const result = await api.applyAdjustment(policy.value.policy_ref, {
      effective_date: adjust.effective_date, changes: changes.value, user: adjust.user
    })
    applied.value = result
    preview.value = null
    adjust.open = false
    await load()
  } catch (err) {
    adjustError.value = errorMessage(err)
  } finally {
    busy.value = false
  }
}

watch(() => route.params.ref, load)
onMounted(load)
</script>

<template>
  <p class="small"><router-link to="/policies">All policies</router-link></p>
  <p v-if="error" class="notice bad" role="alert">{{ error }}</p>

  <template v-if="policy">
    <header class="head">
      <div>
        <h1>{{ policy.insured.name }}</h1>
        <p class="lede">
          {{ policy.policy_ref }}, term {{ policy.term }}. {{ policy.product_name }},
          {{ date(policy.inception_date) }} to {{ date(policy.expiry_date) }}.
        </p>
      </div>
      <span class="status big" :class="statusClass(policy.status)">{{ policy.status_name }}</span>
    </header>

    <p v-if="applied" class="notice good" role="status">
      Adjustment applied as endorsement {{ applied.adjustment.endorsement_number }}.
      <template v-if="applied.adjustment.transaction">
        Heron wrote {{ applied.adjustment.transaction.transaction_ref }} for
        {{ money(applied.adjustment.premium_adjustment) }}.
      </template>
      <template v-else>No premium was charged or returned.</template>
    </p>

    <div class="cols">
      <section class="sheet">
        <h2>Cover</h2>
        <table class="ruled">
          <tbody>
            <tr><td>Trade</td><td>{{ policy.trade_name }}</td></tr>
            <tr><td>Risk postcode</td><td>{{ postcode(policy.risk.postcode) }}</td></tr>
            <template v-if="isProperty">
              <tr><td>Construction</td><td>{{ policy.construction_name }}</td></tr>
              <tr><td>Buildings</td><td class="num">{{ pounds(policy.risk.sum_insured_buildings) }}</td></tr>
              <tr><td>Contents</td><td class="num">{{ pounds(policy.risk.sum_insured_contents) }}</td></tr>
              <tr><td>Business interruption</td><td class="num">{{ pounds(policy.risk.sum_insured_bi) }}</td></tr>
              <tr><td>Voluntary excess</td><td class="num">{{ pounds(policy.risk.voluntary_excess) }}</td></tr>
            </template>
            <template v-else>
              <tr><td>Annual turnover</td><td class="num">{{ pounds(policy.risk.turnover) }}</td></tr>
              <tr><td>Employees</td><td class="num">{{ policy.risk.employees }}</td></tr>
            </template>
            <tr><td>Claims in three years, as keyed in Heron</td><td class="num">{{ policy.risk.claims_count_3y }}</td></tr>
            <tr><td>Broker</td><td>{{ policy.broker.name }} ({{ policy.broker.commission_pct }}%)</td></tr>
          </tbody>
        </table>
      </section>

      <section class="sheet">
        <h2>Premium</h2>
        <table class="ruled">
          <tbody>
            <tr><td>Annual premium</td><td class="num">{{ money(policy.premium.annual_gross) }}</td></tr>
            <tr><td>Insurance Premium Tax</td><td class="num">{{ money(policy.premium.ipt) }}</td></tr>
            <tr><td><strong>Total</strong></td><td class="num"><strong>{{ money(policy.premium.total) }}</strong></td></tr>
          </tbody>
        </table>
        <div v-if="isLive" class="adjust-start">
          <button v-if="!adjust.open" @click="adjust.open = true">Adjust this policy</button>
        </div>
        <p v-else class="small quiet adjust-start">Only a live policy can be adjusted.</p>
      </section>
    </div>

    <section v-if="adjust.open" class="sheet block">
      <h2>Mid-term adjustment</h2>
      <p>Change what is different. The cost is worked out by Heron's own MTAENT routine and shown before anything is saved.</p>
      <div class="adjust">
        <form @submit.prevent>
          <div class="row">
            <div><label for="eff">Change takes effect</label><input id="eff" v-model="adjust.effective_date" type="date" :min="policy.inception_date" :max="policy.expiry_date"></div>
            <div><label for="apc">Risk postcode</label><input id="apc" v-model="adjust.risk.postcode" autocomplete="off"></div>
          </div>
          <template v-if="isProperty">
            <div class="row">
              <div><label for="abld">Buildings sum insured (£)</label><input id="abld" v-model.number="adjust.risk.sum_insured_buildings" type="number" min="0" step="5000"></div>
              <div><label for="acnt">Contents sum insured (£)</label><input id="acnt" v-model.number="adjust.risk.sum_insured_contents" type="number" min="0" step="1000"></div>
            </div>
            <div class="row">
              <div><label for="abi">Business interruption (£)</label><input id="abi" v-model.number="adjust.risk.sum_insured_bi" type="number" min="0" step="5000"></div>
              <div>
                <label for="axs">Voluntary excess</label>
                <select id="axs" v-model.number="adjust.risk.voluntary_excess">
                  <option v-for="x in lookups.voluntary_excesses" :key="x" :value="x">£{{ x.toLocaleString('en-GB') }}</option>
                </select>
              </div>
            </div>
          </template>
          <div v-else class="row">
            <div><label for="ato">Annual turnover (£)</label><input id="ato" v-model.number="adjust.risk.turnover" type="number" min="0" step="5000"></div>
            <div><label for="aem">Employees</label><input id="aem" v-model.number="adjust.risk.employees" type="number" min="1"></div>
          </div>
          <div class="row">
            <div>
              <label for="auser">Signed in as</label>
              <select id="auser" v-model="adjust.user">
                <option value="CLERK1">Branch clerk (CLERK1)</option>
                <option value="UWMGR1">Underwriting manager (UWMGR1)</option>
              </select>
            </div>
          </div>
        </form>

        <div class="result" aria-live="polite">
          <p v-if="adjustError" class="notice bad" role="alert">{{ adjustError }}</p>
          <p v-else-if="!preview" class="quiet">Change a value and the cost appears here.</p>
          <template v-else>
            <table class="ruled">
              <tbody>
                <tr><td>Annual premium now</td><td class="num">{{ money(preview.old_annual_premium) }}</td></tr>
                <tr><td>Annual premium after the change</td><td class="num">{{ money(preview.new_annual_premium) }}</td></tr>
                <tr><td>Days left in the term</td><td class="num">{{ preview.days_remaining }} of 365</td></tr>
                <tr><td>Pro rata {{ preview.premium_adjustment < 0 ? 'return' : 'additional' }} premium</td><td class="num">{{ money(preview.premium_adjustment) }}</td></tr>
                <tr><td>Insurance Premium Tax</td><td class="num">{{ money(preview.ipt_adjustment) }}</td></tr>
                <tr><td><strong>{{ preview.total_adjustment < 0 ? 'To refund' : 'To pay' }}</strong></td><td class="num"><strong>{{ money(Math.abs(preview.total_adjustment)) }}</strong></td></tr>
              </tbody>
            </table>
            <p v-if="preview.waived_as_small" class="small quiet">Adjustments under £10 are not charged or refunded.</p>
          </template>
          <div class="actions">
            <button :disabled="!preview || busy" @click="apply">Apply adjustment</button>
            <button class="secondary" :disabled="busy" @click="adjust.open = false; preview = null">Cancel</button>
          </div>
        </div>
      </div>
    </section>


    <section class="sheet block">
      <h2>Premium transactions</h2>
      <p v-if="!policy.transactions.length" class="quiet">None yet. A quote has no transactions until it is bound.</p>
      <table v-else class="ruled">
        <thead>
          <tr><th>Reference</th><th>Type</th><th>Effective</th><th class="num">Premium</th><th class="num">Tax</th><th class="num">Commission</th><th>Ledger</th></tr>
        </thead>
        <tbody>
          <tr v-for="t in policy.transactions" :key="t.transaction_ref">
            <td>{{ t.transaction_ref }}</td><td>{{ t.type }}</td><td>{{ date(t.effective_date) }}</td>
            <td class="num">{{ money(t.gross_premium) }}</td><td class="num">{{ money(t.ipt) }}</td>
            <td class="num">{{ money(t.commission) }}</td>
            <td>
              <span v-if="t.finance_ref">{{ t.finance_ref }}</span>
              <span v-else class="status todo">Waiting for the overnight file</span>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <section v-if="policy.endorsements.length" class="sheet block">
      <h2>Endorsements</h2>
      <table class="ruled">
        <thead><tr><th>Number</th><th>Effective</th><th>What changed</th><th class="num">Premium</th></tr></thead>
        <tbody>
          <tr v-for="e in policy.endorsements" :key="e.number">
            <td>{{ e.number }}</td><td>{{ date(e.effective_date) }}</td><td>{{ e.detail }}</td>
            <td class="num">{{ money(e.premium_adjustment) }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </template>
</template>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--s4); }
.status.big { font-size: var(--step-1); padding-top: var(--s3); }
.cols { display: grid; grid-template-columns: 1.3fr 1fr; gap: var(--s5); align-items: start; margin-top: var(--s4); }
.block { margin-top: var(--s5); }
.adjust-start { margin: var(--s4) 0 0; }
.adjust { display: grid; grid-template-columns: 1.2fr 1fr; gap: var(--s5); align-items: start; }
.row { display: grid; grid-template-columns: 1fr 1fr; gap: var(--s4); margin-bottom: var(--s4); }
.actions { display: flex; gap: var(--s3); margin-top: var(--s4); }
@media (max-width: 1000px) {
  .cols, .adjust, .row { grid-template-columns: 1fr; }
}
</style>
