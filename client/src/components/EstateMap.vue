<script setup>
// The estate as it is wired today. Solid line = automated, dashed = someone re-keys it.
defineProps({
  systems: { type: Array, default: () => [] }
})

const holds = (systems, key) => (systems.find(s => s.key === key) || {}).holds || ''
</script>

<template>
  <figure class="estate">
    <svg viewBox="0 0 820 330" role="img" aria-labelledby="estate-title estate-desc">
      <title id="estate-title">How the four systems are connected today</title>
      <desc id="estate-desc">
        Heron sends premium transactions to Finance in an overnight file. Referred risks are re-keyed by hand
        into the Underwriting Workbench. Claim counts are re-keyed by hand from the Claims Desk into Heron.
      </desc>
      <defs>
        <marker id="arrow-hand" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path class="head hand" d="M0 0 L10 5 L0 10 z" />
        </marker>
        <marker id="arrow-auto" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path class="head auto" d="M0 0 L10 5 L0 10 z" />
        </marker>
      </defs>

      <g class="link hand">
        <path d="M300 118 C390 92 430 62 526 58" marker-end="url(#arrow-hand)" />
        <text x="322" y="48">referrals, re-keyed by hand</text>
      </g>
      <g class="link hand">
        <path d="M526 165 L304 165" marker-end="url(#arrow-hand)" />
        <text x="322" y="155">claim counts, re-keyed by hand</text>
      </g>
      <g class="link auto">
        <path d="M300 212 C390 238 430 268 526 272" marker-end="url(#arrow-auto)" />
        <text x="322" y="294">premiums, overnight file</text>
      </g>

      <g class="node legacy">
        <rect x="20" y="95" width="280" height="140" rx="3" />
        <text class="name" x="40" y="130">Heron policy admin</text>
        <text class="kind" x="40" y="152">Legacy system of record, since 2004</text>
        <text class="holds" x="40" y="186">{{ holds(systems, 'legacy') }}</text>
        <text class="holds" x="40" y="208">Rating, referral and refund rules in code</text>
      </g>
      <g class="node">
        <rect x="530" y="20" width="270" height="76" rx="3" />
        <text class="name" x="548" y="50">Underwriting Workbench</text>
        <text class="holds" x="548" y="74">{{ holds(systems, 'underwriting') }}</text>
      </g>
      <g class="node">
        <rect x="530" y="127" width="270" height="76" rx="3" />
        <text class="name" x="548" y="157">Claims Desk</text>
        <text class="holds" x="548" y="181">{{ holds(systems, 'claims') }}</text>
      </g>
      <g class="node">
        <rect x="530" y="234" width="270" height="76" rx="3" />
        <text class="name" x="548" y="264">Finance Ledger</text>
        <text class="holds" x="548" y="288">{{ holds(systems, 'finance') }}</text>
      </g>
    </svg>
    <figcaption class="small quiet">
      <span class="key hand"></span> re-keyed by a person &nbsp;&nbsp; <span class="key auto"></span> automated, once a night
    </figcaption>
  </figure>
</template>

<style scoped>
.estate { margin: 0; }
svg { width: 100%; height: auto; display: block; font-family: var(--sans); }
.node rect { fill: var(--surface); stroke: var(--rule); stroke-width: 1; }
.node.legacy rect { fill: var(--ink); stroke: var(--ink); }
.node .name { font-family: var(--serif); font-size: 19px; font-weight: 600; fill: var(--ink); }
.node .kind, .node .holds { font-size: 13px; fill: var(--ink-soft); }
.node.legacy .name { fill: #fff; }
.node.legacy .kind { fill: #a9adf0; }
.node.legacy .holds { fill: #dfe3ee; }
.link path { fill: none; stroke: currentColor; stroke-width: 1.6; }
.link text { font-size: 12.5px; fill: currentColor; font-weight: 600; }
.link.hand { color: var(--amber); }
.link.hand path { stroke-dasharray: 6 5; }
.link.auto { color: var(--dene); }
.head.hand { fill: var(--amber); }
.head.auto { fill: var(--dene); }
.key { display: inline-block; width: 1.8rem; border-top: 2px solid; vertical-align: middle; margin-right: var(--s1); }
.key.hand { border-top-style: dashed; color: var(--amber); }
.key.auto { color: var(--dene); }
figcaption { margin-top: var(--s3); }
</style>
