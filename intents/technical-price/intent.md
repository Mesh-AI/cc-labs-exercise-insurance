# Intent: technical price check (card 3)

## What
- While quoting, the screen shows the Underwriting Workbench's technical price, and how far Heron's quoted premium is from it.
- A quote more than 8% below technical gets a visible warning.
- The warning is advisory only. Heron's price and its accept/refer decision don't change, and no referral is raised.
- If the Workbench isn't answering, the quote still prices and the panel says: "Underwriting Workbench not reachable: no technical price check."

## Why
- Nobody compares Heron's price with underwriting's technical price. Under-priced risks go out marked "Ready to bind", and underwriting only sees a risk if it's referred and re-keyed.
- Showing the gap lets clerks and underwriters spot under-pricing as they quote. A shop in M4 3KV (Manchester) comes out about 11% below technical, and the same shop in S1 2KV (Sheffield) doesn't.

## Constraints
- Don't change `server/legacy/`, the characterisation tests or `server/data/legacy/RATTBL.csv`. Heron's price must stay unchanged.
- Call the Workbench over HTTP only (`ESTATE_BASE_URL`), never by importing `server/systems/`.
- If the Workbench is down, the quote journey must not break.
- New tests must prove the technical price and gap are shown, the warning appears only past 8% below, Heron's price and decision are unchanged, and pricing works with the Workbench down. All existing tests, including the characterisation tests, must still pass.
- Scope: quote pricing only. Out of scope: changing any price, and raising referrals automatically.

## Open questions (for the spec)
1. The Manchester gap comes from a known Heron behaviour (`docs/DOMAIN.md`, item 1): single-letter postcode areas never get their loading. Fixing it is a pricing decision. Record it for Head of Underwriting sign-off, and leave Heron alone.

Approved by Developer Name on 2026-11-17
