# Spec: technical price check (card 3)

Intent: [intent.md](intent.md)

## Summary
When pricing a quote, the new API sends the risk and Heron's annual premium to the Underwriting Workbench. It returns the technical premium and the percentage gap alongside Heron's price. The quote screen shows them in a "Technical price check" panel under the premium schedule, with a warning when the quote is more than 8% below technical. The check is advisory: Heron's price, decision banner and referral rules don't change. If the Workbench doesn't answer, the quote still prices and the panel says so.

Worked example: a shop (RETL, brick, buildings £250,000, contents £60,000, £250 excess, 0 claims).

| Postcode | Heron premium | Technical premium | Gap |
|---|---|---|---|
| M4 3KV (Manchester) | £362.43 | £405.92 | −10.7% |
| S1 2KV (Sheffield) | £362.43 | £362.43 | 0.0% |

## Design

**`server/modern/api.py`** (stdlib `urllib`)
- `_post_assessment(body)`: `POST {ESTATE_BASE_URL}/underwriting/assessments` with a 2 s timeout. Returns the JSON, or raises on any error.
- `_technical_check(risk, quoted_premium)`: sends the risk fields plus `quoted_premium` (Heron's `gross_premium`, which excludes IPT). Returns:
  - On success: `{available: true, technical_premium, quoted_premium, deviation_pct, below_threshold, threshold_pct: 8.0, message: null}`, where `below_threshold` is `deviation_pct < -8.0`.
  - On any error: `{available: false, …, message: "Underwriting Workbench not reachable: no technical price check."}`
- `price_quote` adds `technical` to its response. It runs after Heron prices, on the risk as priced (including the Claims Desk count for existing customers). `price`, `decision` and `decision_reasons` are untouched.
- The Workbench's own `decision` and `reasons` are ignored, so it can never turn a Heron "accept" into a "refer".

**`client/src/components/TechnicalCheck.vue`** (new), shown in `QuoteJourney.vue` under the premium schedule:
- It shows "Underwriting's technical premium (before tax)", "Heron's annual premium (before tax)" and "Gap from technical", signed, to one decimal place. The "before tax" labels keep the technical premium apart from the schedule's "Total to pay".
- If `below_threshold`, a warning notice says: "More than 8% below underwriting's technical price. Worth an underwriter's look before binding." Otherwise a quiet line says it's within 8%.
- If `available` is false, a warning notice shows the message.

**Tests**: new file `tests/backend/test_technical_price.py`.
- The success tests monkeypatch `_post_assessment` to call the real Workbench through the `client` fixture.
- The boundary tests use a stub that returns a fixed deviation.
- The outage test relies on `conftest.py`'s closed-port default.

## Acceptance criteria
- **AC1**: Pricing the Manchester shop returns `technical = {available: true, technical_premium: 405.92, quoted_premium: 362.43, deviation_pct: -10.7, below_threshold: true}`. *Test: `test_manchester_shop_flagged_below_technical`*
- **AC2**: The same shop in Sheffield returns `deviation_pct: 0.0, below_threshold: false`. *Test: `test_sheffield_shop_not_flagged`*
- **AC3**: The threshold is strict: −8.0% isn't flagged, −8.1% is, and +5.0% isn't. *Test: `test_threshold_is_more_than_8_pct_below`*
- **AC4**: Heron's answer doesn't change. In Manchester, `price` is identical with the Workbench up or down, and `decision` stays `accept` with no reasons, even though the Workbench would refer it. *Test: `test_heron_price_and_decision_unchanged`*. The characterisation tests also still pass.
- **AC5**: With the Workbench unreachable, pricing returns 200 with Heron's price, and `technical.available == false` with the message. *Test: `test_workbench_down_still_prices`*
- **AC6**: In the browser, the Manchester shop shows the panel with £405.92, −10.7% and the warning. The Sheffield shop shows 0.0% and no warning. *Check: Playwright script against a running app.*
- **AC7**: The full suite passes: `(cd tests && uv run --project ../server pytest -q)`. The client builds: `(cd client && npm run build)`.
- **AC8**: No protected file changed: `git diff --name-only card-2` shows nothing under `server/legacy/`, `tests/backend/test_characterisation_*` or `server/data/legacy/RATTBL.csv`.

## Areas of concern
1. **The Manchester gap is a Heron pricing defect (Head of Underwriting to decide).** `docs/DOMAIN.md` item 1: Heron looks up the first two characters of the postcode, so single-letter areas (L, M, E, B, G) never get their loading, and these quotes come out about 7% to 15% below technical. This change only makes the gap visible. Fixing it changes live prices and needs Head of Underwriting sign-off, plus finance sign-off for the premium impact. It must not be fixed in Heron as part of this card, and the characterisation tests pin the current behaviour.
2. **A coincidence that can mislead.** In Manchester, Heron's "Total to pay" (premium plus 12% IPT) equals the technical premium (£405.92), because the missing M loading is also 12%. The "before tax" labels on the panel keep the two apart.
3. **Advisory, not a control.** The warning doesn't stop a bind. Making it a referral is a separate decision.
4. **One assessment per keystroke.** `price_quote` runs as the clerk types, and each call creates a Workbench assessment reference. That's harmless in the lab, but a real Workbench might need a dry-run endpoint.
5. **Speed.** Each reprice now makes up to two downstream calls: the Claims Desk and the Workbench. When the Workbench is down, each reprice can wait up to 2 s.

## Out of scope
Changing any price, fixing DOMAIN.md item 1, raising referrals automatically, and running the check on save, bind or mid-term adjustments.

Approved by Developer Name on 2026-11-17

## Proof

| AC | Test or check | Result |
|---|---|---|
| AC1 | `test_technical_price.py::test_manchester_shop_flagged_below_technical` | pass |
| AC2 | `test_technical_price.py::test_sheffield_shop_not_flagged` | pass |
| AC3 | `test_technical_price.py::test_threshold_is_more_than_8_pct_below` (−8.0, −8.1, +5.0) | pass |
| AC4 | `test_technical_price.py::test_heron_price_and_decision_unchanged`; characterisation tests pass | pass |
| AC5 | `test_technical_price.py::test_workbench_down_still_prices` | pass |
| AC6 | Playwright check: `{"manchester":true,"sheffield":true}` | pass |
| AC7 | `(cd tests && uv run --project ../server pytest -q)`: 115 passed; `(cd client && npm run build)`: built | pass |
| AC8 | `git diff --name-only card-2`: `server/modern/api.py`, `client/src/views/QuoteJourney.vue`, new `client/src/components/TechnicalCheck.vue` | pass |
