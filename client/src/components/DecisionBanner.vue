<script setup>
// One sentence on where the quote stands, then the reasons and who gave them.
defineProps({
  decision: { type: String, default: null },
  reasons: { type: Array, default: () => [] }
})

const headline = {
  accept: 'Within branch authority. Ready to bind.',
  refer: 'Needs an underwriter before it can be bound.',
  decline: 'Outside appetite. This risk cannot be written.'
}
const tone = { accept: 'good', refer: 'warn', decline: 'bad' }
</script>

<template>
  <div v-if="decision" class="notice" :class="tone[decision]" role="status">
    <strong>{{ headline[decision] }}</strong>
    <ul v-if="reasons.length">
      <li v-for="(r, i) in reasons" :key="i">{{ r.text }} <span class="source">{{ r.source }}</span></li>
    </ul>
  </div>
</template>

<style scoped>
ul { margin: var(--s2) 0 0; padding-left: var(--s5); }
.source { font-size: var(--step--1); color: var(--ink-soft); border: 1px solid currentColor; border-radius: var(--radius); padding: 0 var(--s1); margin-left: var(--s1); white-space: nowrap; }
</style>
