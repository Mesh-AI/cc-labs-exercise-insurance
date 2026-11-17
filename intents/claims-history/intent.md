# Intent: claims history on the policy (card 5)

## What
- The policy page lists the policy's claims from the Claims Desk, across all terms, newest first: loss date, claim reference, what happened, term, status, paid and outstanding.
- When Heron's keyed claim count for the term shown is lower than the Claims Desk's count of claims in the three years before that term started, the page flags it and says the premium may be too low.
- A policy with no claims shows "No claims".
- If the Claims Desk isn't answering, the policy page still loads and says: "Claims Desk not reachable: claims history not shown."

## Why
- Today the policy page shows only the count someone typed into Heron. To see the claims, staff open the Claims Desk separately.
- Typed counts drift, so terms get priced on too few claims. Varrowstone Builders (LDL0010245) is priced on 0, while the Claims Desk has 2 claims before the current term started.
- Underwriters and service staff see the real claims history where they already look at the policy.

## Constraints
- Don't change `server/legacy/`, the characterisation tests or `server/data/legacy/RATTBL.csv`. Heron's keyed figure isn't changed.
- Call the Claims Desk over HTTP only (`ESTATE_BASE_URL`), never by importing `server/systems/`.
- Compare at the start of the term shown, which is the figure Heron priced on and what data health check W01 uses.
- If the Claims Desk is down, the policy page must still load.
- New tests must prove the claims list, the flag (only when Heron is lower), "No claims", an unchanged Heron figure, and the page loading with the Claims Desk down. All existing tests must still pass.
- Out of scope: changing Heron's figure, comparing earlier terms, and the claim marker (`CLMCUR`).

## Open questions (for the spec)
1. Declined claims: list them but don't count them, as the Claims Desk's own count does? Recommended: yes, with a note under the list.

Approved by Developer Name on 2026-11-17
