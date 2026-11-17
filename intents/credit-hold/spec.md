# Spec: credit hold warning (card 4)

Intent: [intent.md](intent.md)

## Summary
When `price_quote` is called with a `broker_code`, the new API asks the Finance Ledger for that broker's statement. It returns a `broker_credit` object alongside the price. The quote screen shows a warning under the Broker field when the broker has policies on credit hold, with the count and the overdue amount. The warning is advisory: saving and binding are unchanged. A broker in good standing, or one with no ledger history, shows nothing. If the ledger doesn't answer, quoting still works and the screen says the credit status wasn't checked.

Ledger figures at the lab date:

| Broker | Policies on credit hold | Overdue | Net outstanding |
|---|---|---|---|
| B004 Ivern Insurance Services | 19 | £66,486.68 | £59,212.77 |
| B001 Draven Broking | 0 | £0.00 | −£4,466.96 (in credit) |

## Design

**`server/modern/api.py`** (stdlib `urllib`)
- `_ledger_get(path)`: `GET {ESTATE_BASE_URL}{path}` with a 2 s timeout. Returns `(status, json)`, and returns an HTTP error status, such as 404, as a status rather than raising. Raises on connection errors.
- `_fetch_broker_statement(broker_code)`: calls `_ledger_get('/finance/brokers/BRK-{code}/statement')`. Returns the JSON, or `None` on 404 (no ledger history). Raises on any other non-200 status.
- `_broker_credit(broker_code)`:
  - No broker chosen: `None`.
  - Statement found, or 404: `{checked: true, on_hold, policies_on_credit_hold, overdue_amount, message: null}`, where `on_hold` is `policies_on_credit_hold > 0`. A 404 gives `on_hold: false` and zeros.
  - Any other error or timeout: `{checked: false, on_hold: false, policies_on_credit_hold: null, overdue_amount: null, message: "Finance Ledger not reachable: broker credit status not checked."}`
- `price_quote` adds `broker_credit` to its response. `price`, `decision`, `decision_reasons`, `claims_count` and `technical` are unchanged.

**`client/src/views/QuoteJourney.vue`**, under the Broker select:
- If `on_hold`, a warning notice: "**On credit hold:** {n} policies unpaid for more than 60 days, {overdue} overdue. Check with credit control before placing more business."
- If `checked` is false, a warning notice shows the message.
- Otherwise nothing shows. The Save and Bind buttons are untouched.

**Tests**: new file `tests/backend/test_credit_hold.py`.
- The tests monkeypatch `_ledger_get` to call the real Finance Ledger through the `client` fixture, so the 404 handling in `_fetch_broker_statement` runs for real.
- The outage test relies on `conftest.py`'s closed-port default.

## Acceptance criteria
- **AC1**: Pricing with `broker_code: "B004"` returns `broker_credit = {checked: true, on_hold: true, policies_on_credit_hold: 19, overdue_amount: 66486.68, message: null}`. *Test: `test_broker_on_credit_hold_is_flagged`*
- **AC2**: Pricing with `broker_code: "B001"` returns `on_hold: false`, with 0 policies on hold. *Test: `test_broker_in_good_standing_shows_nothing`*
- **AC3**: Pricing with a broker the ledger has no postings for (B999, which gets a 404) returns `checked: true, on_hold: false`. *Test: `test_broker_without_ledger_history_shows_nothing`*
- **AC4**: Pricing with no broker returns `broker_credit: null`. *Test: `test_no_broker_no_check`*
- **AC5**: With the ledger unreachable, pricing for B004 returns 200 with Heron's price, and `broker_credit.checked == false` with the message. *Test: `test_ledger_down_still_prices`*
- **AC6**: The warning doesn't change the quote. B004's `price`, `decision` and `decision_reasons` are identical with the ledger up or down, and a B004 quote can still be saved (201). *Test: `test_warning_does_not_block_or_change_price`*
- **AC7**: In the browser, choosing B004 shows the warning with "19 policies" and "£66,486.68", with Save quote still enabled. Choosing B001 shows no warning. *Check: Playwright script against a running app.*
- **AC8**: The full suite passes: `(cd tests && uv run --project ../server pytest -q)`. The client builds: `(cd client && npm run build)`.
- **AC9**: No protected file changed: `git diff --name-only card-3` shows nothing under `server/legacy/`, `tests/backend/test_characterisation_*` or `server/data/legacy/RATTBL.csv`.

## Areas of concern
1. **Warn or block (Head of Credit Control to decide).** This change only warns. Blocking a save or bind for a broker on credit hold is a credit control decision, and it would be a separate change.
2. **Overdue is more than outstanding.** The ledger's `overdue_amount` sums only the policies on hold. Its `outstanding` nets in credits on other policies: B004 has £66,486.68 overdue against £59,212.77 net. The screen shows the overdue figure, and credit control should confirm that.
3. **The warning appears once the quote is priced.** If a clerk picks a broker before filling in the risk, nothing shows until there's a price. That still meets "before the quote is saved".
4. **One more HTTP call per reprice.** Pricing now makes up to three downstream calls: the Claims Desk, the Workbench and the ledger. The statement call is the heaviest, because it scans every posting for the broker. When the ledger is down, each reprice can wait up to 2 s.
5. **The 60-day rule belongs to the ledger.** The API trusts the ledger's `credit_hold` flag, so if finance changes the rule, it flows through without a code change.

## Out of scope
Blocking the save or bind, chasing payment, showing net outstanding or the list of overdue policies, and suspended brokers.

Approved by Developer Name on 2026-11-17

## Proof

| AC | Test or check | Result |
|---|---|---|
| AC1 | `test_credit_hold.py::test_broker_on_credit_hold_is_flagged` | pass |
| AC2 | `test_credit_hold.py::test_broker_in_good_standing_shows_nothing` | pass |
| AC3 | `test_credit_hold.py::test_broker_without_ledger_history_shows_nothing` (B999 → 404) | pass |
| AC4 | `test_credit_hold.py::test_no_broker_no_check` | pass |
| AC5 | `test_credit_hold.py::test_ledger_down_still_prices` | pass |
| AC6 | `test_credit_hold.py::test_warning_does_not_block_or_change_price` | pass |
| AC7 | Playwright check: `{"b004":true,"b004CanSave":true,"b001":true}` | pass |
| AC8 | `(cd tests && uv run --project ../server pytest -q)`: 121 passed; `(cd client && npm run build)`: built | pass |
| AC9 | `git diff --name-only card-3`: only `server/modern/api.py` and `client/src/views/QuoteJourney.vue` | pass |
