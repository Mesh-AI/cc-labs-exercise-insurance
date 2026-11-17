# Intent: premium to finance at bind (card 2)

## What
- Binding a policy posts Heron's new business premium transaction to the Finance Ledger straight away.
- The ledger reference shows on the "Policy is live" panel and in the policy page's Ledger column, in place of "Waiting for the overnight file".
- Posting the same transaction twice doesn't double count.
- If the Finance Ledger isn't answering, binding still succeeds and the screen says: "Finance Ledger not reachable: the premium will go in the overnight file."

## Why
- Today finance only receives a bound premium in the overnight file, so the ledger and broker balances lag by a day, and the policy page shows "Waiting for the overnight file".
- Finance and credit control get premiums the moment a policy goes live. Staff can see on the policy that it's been posted.

## Constraints
- To show the reference, stamp it on Heron's transaction with the existing `adapter.stamp_finance_ref()`, the same thing the overnight job does. Go through the adapter, never `server/legacy/`.
- Don't change `server/legacy/`, the characterisation tests or `server/data/legacy/RATTBL.csv`.
- Call the Finance Ledger over HTTP only (`ESTATE_BASE_URL`), never by importing `server/systems/`.
- If the ledger is down, the bind journey must not break.
- New tests must prove the posting matches Heron's premium, tax and commission, that a repeat post doesn't double count, and that binding works with the ledger down. All existing tests must still pass.
- Scope: new business binds only. Out of scope: mid-term adjustments, cancellations, and building or changing an overnight job.

## Open questions (for the spec)
1. Once postings go in real time, should the overnight file skip transactions that already have a ledger reference? Finance must sign this off. Nothing changes here, because there is no overnight job in this repo, and the ledger's idempotency on `transaction_ref` protects the totals either way.

Approved by Developer Name on 2026-11-17
