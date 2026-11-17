<script setup>
// Underwriting's technical price next to Heron's, and how far apart they are.
// Advice only: it never changes the price or the decision.
import { computed } from 'vue'
import { money } from '../utils/format'

const props = defineProps({
  check: { type: Object, default: null }
})

const gap = computed(() => {
  const d = props.check?.deviation_pct
  if (d === null || d === undefined) return ''
  return (d < 0 ? '−' : d > 0 ? '+' : '') + Math.abs(d).toFixed(1) + '%'
})
</script>

<template>
  <section v-if="check" class="technical sheet" aria-live="polite">
    <h3>Technical price check</h3>
    <template v-if="check.available">
      <table>
        <tbody>
          <tr><td>Underwriting's technical premium (before tax)</td><td class="num">{{ money(check.technical_premium) }}</td></tr>
          <tr><td>Heron's annual premium (before tax)</td><td class="num">{{ money(check.quoted_premium) }}</td></tr>
          <tr class="gap" :class="{ below: check.below_threshold }"><td>Gap from technical</td><td class="num">{{ gap }}</td></tr>
        </tbody>
      </table>
      <p v-if="check.below_threshold" class="notice warn small" role="status">
        More than {{ check.threshold_pct }}% below underwriting's technical price. Worth an underwriter's look before binding.
      </p>
      <p v-else class="small quiet">Within {{ check.threshold_pct }}% of the technical price.</p>
    </template>
    <p v-else class="notice warn small" role="status">{{ check.message }}</p>
  </section>
</template>

<style scoped>
.technical h3 { font-size: var(--step-0); margin-bottom: var(--s3); }
table { width: 100%; border-collapse: collapse; margin-bottom: var(--s3); }
td { padding: var(--s1) 0; border-bottom: 1px dotted var(--rule); vertical-align: baseline; }
td.num { text-align: right; padding-left: var(--s4); white-space: nowrap; }
.gap td { font-weight: 600; border-bottom: 0; }
.gap.below td { color: var(--rust); }
p { margin: 0; }
</style>
