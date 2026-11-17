# Spec: premium to finance at bind (card 2)

Intent: [intent.md](intent.md)

## Summary
After Heron binds a quote, the new API posts the new business transaction to the Finance Ledger over HTTP. It then stamps the returned `posting_ref` on Heron's transaction, so the "Policy is live" panel and the policy page's Ledger column show it. The ledger is idempotent on `transaction_ref`, so a repeat post returns the original posting and is never counted twice. If the ledger doesn't answer, the bind still succeeds and the screen says the premium will go in the overnight file.

## Design

**`server/modern/api.py`** (stdlib `urllib`)
- `_post_to_ledger(posting)`: `POST {ESTATE_BASE_URL}/finance/postings` with a JSON body and a 2 s timeout. Returns the JSON, or raises on any error.
- `_send_to_finance(trn, policy)`: builds the posting from Heron's transaction and the policy, using the same field mapping as data health check E19:

  | Posting field | Taken from |
  |---|---|
  | `transaction_ref` | `trn.transaction_ref` |
  | `policy_ref` | `policy.policy_ref` |
  | `policy_term` | `trn.term` |
  | `broker_account` | `policy.broker.account` |
  | `transaction_type` | `trn.type` |
  | `effective_date` | `trn.effective_date` |
  | `gross_premium`, `ipt`, `commission` | the same fields on `trn` |

  - On success: calls `adapter.stamp_finance_ref(trn.number, posting_ref)` and returns `{posted: true, posting_ref, duplicate, message: null}`.
  - On any error: returns `{posted: false, posting_ref: null, duplicate: false, message: "Finance Ledger not reachable: the premium will go in the overnight file."}`.
- `bind_quote`: Heron binds, then `_send_to_finance` runs, then the endpoint returns `{policy, transaction, finance}`. The transaction carries `finance_ref` when posted.

**`client/src/views/QuoteJourney.vue`**, the "Policy is live" panel:
- If the post succeeded: "Posted to the Finance Ledger as **GL-…**."
- If not: a warning notice with the message.

**`client/src/views/Policy.vue`**: no change. The Ledger column already shows `finance_ref` when it's set.

**Tests**: new file `tests/backend/test_premium_to_finance.py`.
- The success tests monkeypatch `_post_to_ledger` to call the real Finance Ledger through the `client` fixture.
- The outage test relies on `conftest.py`'s closed-port default.
- An autouse fixture snapshots the ledger's in-memory postings and restores them after each test. Every fresh `heron_db` copy issues the same next transaction number, so without the restore the tests would leak into each other.

## Acceptance criteria
- **AC1**: Binding a new quote returns `finance.posted == true` with a `GL-` posting ref. `GET /finance/ledger?transaction_ref=…` returns exactly one posting for that transaction, with the same policy, term, broker account, type, effective date, premium, tax and commission as Heron's transaction. *Test: `test_bind_posts_matching_premium_to_ledger`*
- **AC2**: After the bind, `GET /api/v1/policies/{ref}` shows the transaction with `finance_ref` equal to the posting ref. *Test: `test_policy_shows_ledger_reference`*
- **AC3**: Sending the same transaction again returns `duplicate: true` with the same posting ref, and the ledger still has exactly one posting for it. *Test: `test_repeat_post_does_not_double_count`*
- **AC4**: With the ledger unreachable, binding returns 200, the policy is live (status `L`) with a Heron transaction, `finance.posted == false` with the overnight-file message, `finance_ref` is empty, and the ledger has no posting. *Test: `test_bind_succeeds_when_ledger_down`*
- **AC5**: In the browser, binding a new quote shows "Posted to the Finance Ledger as GL-…" on the live panel, and the policy page's Ledger column shows that ref instead of "Waiting for the overnight file". *Check: Playwright script against a running app.*
- **AC6**: The full suite passes: `(cd tests && uv run --project ../server pytest -q)`. The client builds: `(cd client && npm run build)`.
- **AC7**: No protected file changed: `git diff --name-only card-1` shows nothing under `server/legacy/`, `tests/backend/test_characterisation_*` or `server/data/legacy/RATTBL.csv`.

## Areas of concern
1. **The overnight file (finance to sign off).** With real-time posting, the overnight file must not post the same transaction again. The ledger's idempotency protects the totals either way, but whether the job should skip transactions that already have a `FINREF` is finance's decision. There's no overnight job in this repo, so nothing changes here.
2. **Writing to Heron.** Stamping `FINREF` writes to Heron's `PRMTRN` table, through the existing adapter function and not `server/legacy/`. It's what the overnight job would have done.
3. **Partial failure.** If the post succeeds but the stamp fails, the ledger has the posting and Heron doesn't show it. The overnight file would re-send it, and idempotency absorbs the duplicate.
4. **Ledger rejections.** The ledger rejects IPT that isn't within a penny of 12%. Heron's figures should always pass, but a 422 is treated like an outage, so the bind succeeds and the "not reachable" wording would then be slightly inaccurate.
5. **Lab data is in memory.** Postings and stamps last only until the server restarts. Data health reads the files on disk, so it won't see them.

## Out of scope
Mid-term adjustments, cancellations, building or changing an overnight job, and retrying failed posts.

Approved by Developer Name on 2026-11-17

## Proof

| AC | Test or check | Result |
|---|---|---|
| AC1 | `test_premium_to_finance.py::test_bind_posts_matching_premium_to_ledger` | pass |
| AC2 | `test_premium_to_finance.py::test_policy_shows_ledger_reference` | pass |
| AC3 | `test_premium_to_finance.py::test_repeat_post_does_not_double_count` | pass |
| AC4 | `test_premium_to_finance.py::test_bind_succeeds_when_ledger_down` | pass |
| AC5 | Playwright check: `{"livePanelRef":true,"policyPageRef":true}` | pass |
| AC6 | `(cd tests && uv run --project ../server pytest -q)`: 108 passed; `(cd client && npm run build)`: built | pass |
| AC7 | `git diff --name-only card-1`: only `server/modern/api.py` and `client/src/views/QuoteJourney.vue` | pass |
