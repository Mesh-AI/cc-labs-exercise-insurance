# Card 3: technical price check

**Size:** medium, suits block 2. **Connects to:** Underwriting Workbench.

## Today
Nobody compares the price Heron quotes with underwriting's technical price. Underwriting only sees a risk if it is referred and re-keyed.

![Quote for a shop in M4 3KV: annual premium £362.43 and Within branch authority, Ready to bind](img/card-3-today-1-manchester-ready-to-bind.png)
*A shop in Manchester (M4 3KV) is quoted at £362.43 a year, and the screen says it's ready to bind. Nothing on screen compares it with underwriting's price.*

![Underwriting Workbench assessment of the same shop: technical premium 405.92, deviation -10.7, decision refer](img/card-3-today-2-workbench-says-below.png)
*Underwriting's Workbench would price the same shop at £405.92. The quote is 10.7% below technical, and the Workbench would refer it. Nobody asks.*

## The change
While quoting, the screen shows underwriting's technical price and how far the quoted premium is from it, and flags a quote more than 8% below technical.

![Manchester shop quote with a Technical price check panel: technical £405.92, Heron £362.43, gap -10.7% and a warning](img/card-3-change-1-manchester-flagged.png)
*After the change, the quote shows the technical price beside Heron's and warns when it's more than 8% below. The warning is advice only: Heron's price and decision are unchanged.*

![The same shop in S1 2KV: technical £362.43, Heron £362.43, gap 0.0%, within 8%](img/card-3-change-2-sheffield-ok.png)
*The same shop in Sheffield (S1 2KV) matches the technical price exactly. Only single-letter postcode areas like M are out (see `docs/DOMAIN.md`, item 1).*

![Manchester shop quote with the Workbench down: the panel says Underwriting Workbench not reachable, and the premium still shows](img/card-3-change-3-workbench-down.png)
*If the Workbench doesn't answer, the quote still prices and the panel says there's no technical price check.*

## Where to look
- `server/modern/api.py`: `price_quote`
- Underwriting Workbench: `POST /api/systems/underwriting/assessments` with the risk and `quoted_premium`, returns `technical_premium` and `deviation_from_technical_pct`
- `client/src/views/QuoteJourney.vue`: the right-hand column under the premium schedule

## Done when
- Every priced quote shows the technical price and the gap, with a warning past 8% below.
- If the Workbench is not answering, the quote still prices and the panel says so.
- Heron's price is unchanged: the characterisation tests still pass.
- New tests prove the above.

Try it on a shop in **M4 3KV** (Manchester), then the same shop in **S1 2KV** (Sheffield).

## A good spec will catch
Manchester quotes come out about 11% below technical and Sheffield ones do not. The cause is a known Heron behaviour (`docs/DOMAIN.md`, item 1). The fix is a pricing decision, so the spec should record it for underwriting sign-off and leave Heron alone.

## Out of scope
Changing any price, and raising referrals automatically.
