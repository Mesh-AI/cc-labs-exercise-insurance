<script setup>
// The premium, set out the way it appears on a policy schedule: what was rated,
// what was applied to it, and what the customer pays. One job: show the working.
import { money, pounds, factor } from '../utils/format'

defineProps({
  price: { type: Object, default: null },
  stale: { type: Boolean, default: false }
})
</script>

<template>
  <section class="schedule" :class="{ stale }" aria-live="polite">
    <h2>Premium schedule</h2>
    <p v-if="!price" class="quiet">Fill in the risk and the price appears here, line by line.</p>
    <template v-else>
      <table>
        <tbody>
          <tr v-for="line in price.schedule.lines" :key="line.label">
            <td>
              {{ line.label }}
              <span class="working">
                <template v-if="line.rate_per_employee">{{ line.basis }} staff at {{ money(line.rate_per_employee) }}</template>
                <template v-else>{{ pounds(line.basis) }} at {{ line.rate_per_1000.toFixed(2) }} per £1,000</template>
              </span>
            </td>
            <td class="num">{{ money(line.amount) }}</td>
          </tr>
          <tr class="subtotal">
            <td>Base premium</td><td class="num">{{ money(price.schedule.base_premium) }}</td>
          </tr>
          <tr v-for="f in price.schedule.factors" :key="f.label" class="factor" :class="{ neutral: f.factor === 1 }">
            <td>{{ f.label }}</td><td class="num">{{ factor(f.factor) }}</td>
          </tr>
          <tr v-if="price.schedule.minimum_premium_applied" class="factor">
            <td>Minimum premium applies</td><td class="num">{{ money(price.schedule.minimum_premium) }}</td>
          </tr>
          <tr class="subtotal">
            <td>Annual premium</td><td class="num">{{ money(price.gross_premium) }}</td>
          </tr>
          <tr>
            <td>Insurance Premium Tax at 12%</td><td class="num">{{ money(price.ipt) }}</td>
          </tr>
          <tr class="total">
            <td>Total to pay</td><td class="num">{{ money(price.total_payable) }}</td>
          </tr>
        </tbody>
      </table>
      <p class="small quiet source">
        Priced by Heron's own rating routine, so this is the figure the legacy screen gives.
        <template v-if="price.commission !== undefined">Broker commission {{ money(price.commission) }}.</template>
      </p>
    </template>
  </section>
</template>

<style scoped>
.schedule { background: var(--surface); border: 1px solid var(--rule); border-top: 4px solid var(--ink); padding: var(--s5); transition: opacity 0.15s; }
.schedule.stale { opacity: 0.55; }
h2 { font-size: var(--step-1); margin-bottom: var(--s4); }
table { width: 100%; border-collapse: collapse; }
td { padding: var(--s2) 0; vertical-align: baseline; border-bottom: 1px dotted var(--rule); }
td.num { padding-left: var(--s4); }
.working { display: block; font-size: var(--step--1); color: var(--ink-soft); }
.subtotal td { font-weight: 600; border-bottom: 1px solid var(--ink); }
.factor td { color: var(--ink); }
.factor.neutral td { color: var(--ink-soft); }
.total td { font-family: var(--serif); font-size: var(--step-2); font-weight: 600; border-bottom: 3px double var(--ink); padding-top: var(--s3); }
.source { margin: var(--s4) 0 0; }
</style>
