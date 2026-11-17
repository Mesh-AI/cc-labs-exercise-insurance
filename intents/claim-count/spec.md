# Spec: claim count from the Claims Desk (card 1)

Intent: [intent.md](intent.md)

## Summary
For an existing customer, the new API asks the Claims Desk for `claims_count_3y` and prices on that figure, whatever was typed. Both pricing and saving a quote do this, so the saved Heron quote carries the same count as the price shown. The quote screen shows the figure read-only, labelled "From Claims Desk". New customers still type it. If the Claims Desk doesn't answer, pricing uses the typed figure and the screen says so.

Known case: Varrowstone Builders (insured `4000218`). Heron has `CLMCNT3 = 0`, and the Claims Desk returns `claims_count_3y = 2`.

## Design

**`server/modern/api.py`** (no new dependencies; uses stdlib `urllib`)
- `_fetch_claims_experience(insured_ref)`: `GET {ESTATE_BASE_URL}/claims/experience?insured_ref=…`. `ESTATE_BASE_URL` is read at call time and defaults to `http://localhost:8001/api/systems`. Timeout is 2 s. Returns the JSON, or raises on any error.
- `_resolve_claims_count(risk, insured_ref)`:
  - No `insured_ref`: keep the typed figure, `source: "typed"`, no HTTP call.
  - Claims Desk answers: set `risk.claims_count_3y` to its count, `source: "claims_desk"`.
  - Any error or timeout: keep the typed figure, `source: "typed"`, `claims_desk_unavailable: true`, `message: "Claims Desk not reachable: priced on the typed figure."`
- `price_quote` and `create_quote` call it before pricing or saving. Both responses gain `claims_count: {value, source, claims_desk_unavailable, message}`.

**`client/src/views/QuoteJourney.vue`**
- If `priced.claims_count.source` is `claims_desk` and the customer is existing, the claims input is read-only, shows the value, and has the hint "From Claims Desk". The read-only input has a tinted background so it doesn't look editable.
- If `claims_desk_unavailable` is true, the input stays editable and a warning notice shows the message.
- New customers see the field unchanged.

**`client/src/components/PremiumSchedule.vue`**: no change. Heron's factor line "Claims in last three years: N" already shows the count used.

**Tests**: new file `tests/backend/test_claim_count.py`.
- The success tests monkeypatch `_fetch_claims_experience` to call the real Claims Desk through the `client` fixture.
- The outage tests rely on `conftest.py`'s default `ESTATE_BASE_URL`, a closed port, so they exercise the real HTTP failure path.

## Acceptance criteria
- **AC1**: Pricing Varrowstone (`insured_ref=4000218`) with 0 typed returns `claims_count = {value: 2, source: "claims_desk"}`. The schedule factors include "Claims in last three years: 2", and the premium equals pricing the same risk with 2 typed. *Test: `test_existing_customer_priced_on_claims_desk_count`*
- **AC2**: Pricing a new customer (no `insured_ref`) with 3 typed uses 3, `source: "typed"`, and makes no Claims Desk call. *Test: `test_new_customer_uses_typed_count`*
- **AC3**: With the Claims Desk unreachable, pricing Varrowstone with 1 typed returns 200, uses 1, and carries `claims_desk_unavailable: true` and the message. *Test: `test_claims_desk_down_falls_back_to_typed`*
- **AC4**: `create_quote` for Varrowstone with 0 typed saves a Heron quote whose risk has `claims_count_3y == 2`, and whose saved premium matches the priced premium. *Test: `test_saved_quote_carries_claims_desk_count`*
- **AC5**: `create_quote` with the Claims Desk unreachable still saves, using the typed figure. *Test: `test_create_quote_when_claims_desk_down`*
- **AC6**: In the browser, choosing Varrowstone as an existing customer makes the claims field read-only, shows 2 and "From Claims Desk", and the premium schedule shows "Claims in last three years: 2". *Check: Playwright script against a running app.*
- **AC7**: The full suite passes: `(cd tests && uv run --project ../server pytest -q)`. The client builds: `(cd client && npm run build)`.
- **AC8**: No protected file changed: `git diff --name-only harness` shows nothing under `server/legacy/`, `tests/backend/test_characterisation_*` or `server/data/legacy/RATTBL.csv`.

## Areas of concern
1. **Per customer, not per policy (underwriting to confirm).** The Claims Desk counts every claim on the insured. Heron's `CLMCNT3` and data health check W01 count per policy. A customer with both a CP and a CL policy gets claims from the other product counted, which can raise their price.
2. **Source of truth.** The Claims Desk wins with no override. If underwriting later wants an override, it needs a reason and an audit trail, which is a separate change.
3. **Every keystroke now makes an HTTP call.** `price_quote` reprices as the clerk types, so each reprice now calls the Claims Desk too. A 2 s timeout keeps the screen usable when it's down, but each reprice can still wait up to 2 s.
4. **The backend calls itself.** In the lab, the Claims Desk runs in the same process. ARCHITECTURE.md requires HTTP anyway, which is fine under uvicorn, but tests must supply the Claims Desk answer themselves.
5. **Lab clock.** The Claims Desk counts to its own "today", which is frozen at 2026-11-12, not to the quote's inception date.

## Out of scope
Renewals, mid-term adjustments, writing the count to the insured's record, and an underwriter override.

Approved by Developer Name on 2026-11-17

## Proof

| AC | Test or check | Result |
|---|---|---|
| AC1 | `test_claim_count.py::test_existing_customer_priced_on_claims_desk_count` | pass |
| AC2 | `test_claim_count.py::test_new_customer_uses_typed_count` | pass |
| AC3 | `test_claim_count.py::test_claims_desk_down_falls_back_to_typed` | pass |
| AC4 | `test_claim_count.py::test_saved_quote_carries_claims_desk_count` | pass |
| AC5 | `test_claim_count.py::test_create_quote_when_claims_desk_down` | pass |
| AC6 | Playwright check: `{"readOnly":true,"value2":true,"fromClaimsDesk":true,"factor2":true}` | pass |
| AC7 | `(cd tests && uv run --project ../server pytest -q)`: 104 passed; `(cd client && npm run build)`: built | pass |
| AC8 | `git diff --name-only harness`: only `server/modern/api.py` and `client/src/views/QuoteJourney.vue` | pass |
