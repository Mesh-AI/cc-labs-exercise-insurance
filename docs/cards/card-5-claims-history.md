# Card 5: claims history on the policy

**Size:** medium, suits block 2. **Connects to:** Claims Desk.

## Today
The policy page shows only the claim count someone typed into Heron. To see the claims, staff open the Claims Desk separately.

## The change
The policy page lists the policy's claims from the Claims Desk (loss date, what happened, status, paid and outstanding), and flags when Heron's typed claim count is lower than the Claims Desk shows.

## Where to look
- `server/modern/api.py`: `get_policy`
- Claims Desk: `GET /api/systems/claims/claims?policy_ref=` and `GET /api/systems/claims/experience?policy_ref=&as_at=`
- `client/src/views/Policy.vue`

## Done when
- The claims list appears on the policy page, and the flag shows where the counts differ.
- If the Claims Desk is not answering, the policy page still loads.
- New tests prove both, and every existing test still passes.

Try **Varrowstone Builders**.

## A good spec will ask
Compare at which date? Heron priced the term on the count at inception, so the fair comparison is the claims in the three years before the term started.

## Out of scope
Changing Heron's figure.
