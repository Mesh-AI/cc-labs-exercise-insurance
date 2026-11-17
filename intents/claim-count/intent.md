# Intent: claim count from the Claims Desk (card 1)

## What
- When a new business quote is for an existing customer, the price uses the Claims Desk's "claims in the last three years" instead of the figure the user typed.
- The quote screen shows that figure as read-only, with where it came from.
- New customers still type the figure.
- A saved quote stores the Claims Desk count, so the saved price matches the price shown.
- If the Claims Desk isn't answering, pricing uses the typed figure, the field stays editable, and the screen says: "Claims Desk not reachable: priced on the typed figure."

## Why
- Clerks copy the count by hand from the Claims Desk, and Heron prices on whatever was typed. The figure drifts: the Data health page already lists policies where the typed count is lower than the Claims Desk's, so those risks are under-priced.
- Varrowstone Builders (insured 4000218) is a known case: Heron has 0 claims, and the Claims Desk has 2.
- Underwriting benefits from prices based on the system of record. Clerks stop re-keying.

## Constraints
- The Claims Desk is the source of truth when the counts disagree, with no override. Underwriting owns this decision.
- Don't change `server/legacy/`, the characterisation tests or `server/data/legacy/RATTBL.csv`. The insured's record in Heron isn't updated.
- Call the Claims Desk over HTTP only (`ESTATE_BASE_URL`), never by importing `server/systems/`.
- If the Claims Desk is down, the quote journey must not break.
- New tests must prove the Claims Desk count is used, new customers are unaffected, and the fallback works. All existing tests must still pass.
- Scope: new business quotes only (pricing, saving and the quote screen). Out of scope: renewals, mid-term adjustments, and writing the count back to the insured's record.

## Open questions (for the spec)
1. The Claims Desk counts claims per insured, while Heron's figure is per policy. A customer with several policies may get a higher count. Is that intended?
2. Every reprice adds a call to the Claims Desk. What timeout is acceptable while the clerk types?

Approved by Developer Name on 2026-11-17
