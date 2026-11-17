# Spec: claims history on the policy (card 5)

Intent: [intent.md](intent.md)

## Summary
`GET /api/v1/policies/{ref}` gains a `claims` block from the Claims Desk:
- the policy's claims across all terms, newest first;
- the Claims Desk's count of claims in the three years before the term shown started;
- a flag when Heron's keyed count is lower.

The policy page shows them in a new "Claims" section. If the Claims Desk doesn't answer, the policy still loads and the section says so. Heron's keyed figure isn't changed.

Example policies:

| Policy | Insured | Heron keyed | Claims Desk before inception | Claims on policy |
|---|---|---|---|---|
| LDL0010245, term 3 from 24 Aug 2026 | Varrowstone Builders | 0 | 2 | 2: 9 Aug 2026 open, £8,645.04 outstanding; 26 Apr 2026 settled, £17,590.29 paid |
| LDL0010003 | Varrowwick Books | 1 | 1 | 1 (counts agree, no flag) |
| LDC0010001 | Kestrowcroft Beauty Rooms | 0 | 0 | none ("No claims") |

## Design

**`server/modern/api.py`** (stdlib `urllib`)
- `_claims_desk_get(path, params)`: `GET {ESTATE_BASE_URL}/claims{path}?…` with a 2 s timeout. Returns the JSON, or raises on any error.
- `_claims_history(policy)` makes two calls:
  - `GET /claims/claims?policy_ref=…` for the list.
  - `GET /claims/experience?policy_ref=…&as_at=<day before inception>` for the count. Using the day before inception means a loss on the new term's first day isn't counted against that term's own price.

  It returns:
  - On success: `{available: true, claims: [{claim_ref, loss_date, description, term, status, paid, outstanding}], heron_count, claims_desk_count, compared_as_at, inception_date, lower_in_heron, message: null}`, where `lower_in_heron` is `heron_count < claims_desk_count`.
  - On any error: `{available: false, claims: [], …, lower_in_heron: false, message: "Claims Desk not reachable: claims history not shown."}`
- `get_policy` returns `{**policy_view, 'claims': _claims_history(policy_view)}`. Nothing else in the policy view changes.

**`client/src/views/Policy.vue`**: a new "Claims" section after Premium transactions.
- If `lower_in_heron`, a warning notice: "Heron has {heron_count} claims keyed for this term, but the Claims Desk shows {claims_desk_count} in the three years before cover started on {inception}. The premium may be too low." The Cover table's "as keyed in Heron" row is also tinted in the warning colour.
- A table of Loss date, Claim, What happened, Term, Status, Paid and Outstanding, or "No claims." when empty. Under it, a quiet note: "From the Claims Desk. Declined claims are listed but not counted."
- If `available` is false, a warning notice shows the message.

**Tests**: new file `tests/backend/test_claims_history.py`.
- The success tests monkeypatch `_claims_desk_get` to call the real Claims Desk through the `client` fixture.
- The outage test relies on `conftest.py`'s closed-port default.

## Acceptance criteria
- **AC1**: `GET /api/v1/policies/LDL0010245` returns `claims.available == true` with exactly 2 claims, newest first:
  - `CLM-2026-000124` (2026-08-09, open, outstanding 8645.04)
  - `CLM-2026-000112` (2026-04-26, settled, paid 17590.29)

  Each has a description and term. *Test: `test_policy_lists_claims_from_claims_desk`*
- **AC2**: For LDL0010245, `heron_count == 0`, `claims_desk_count == 2`, `compared_as_at == "2026-08-23"`, `lower_in_heron == true`, and `risk.claims_count_3y` is still 0. *Test: `test_flags_when_heron_count_is_lower`*
- **AC3**: For LDL0010003, where the counts agree, `lower_in_heron == false`. *Test: `test_no_flag_when_counts_agree`*
- **AC4**: For LDC0010001, `claims == []` and `lower_in_heron == false`. *Test: `test_policy_with_no_claims`*
- **AC5**: With the Claims Desk unreachable, `GET /api/v1/policies/LDL0010245` returns 200 with the full policy, and `claims.available == false` with the message. *Test: `test_policy_loads_when_claims_desk_down`*
- **AC6**: In the browser, LDL0010245's policy page shows the Claims section with both claims and the flag text, and LDC0010001 shows "No claims". *Check: Playwright script against a running app.*
- **AC7**: The full suite passes: `(cd tests && uv run --project ../server pytest -q)`. The client builds: `(cd client && npm run build)`.
- **AC8**: No protected file changed: `git diff --name-only card-4` shows nothing under `server/legacy/`, `tests/backend/test_characterisation_*` or `server/data/legacy/RATTBL.csv`.

## Areas of concern
1. **Edge of the three-year window.** Data health W01 counts losses strictly between inception minus three years and inception. The Claims Desk's experience endpoint, with `as_at` set to the day before inception, also includes a loss on exactly the date three years before inception. This could cause a one-claim disagreement in a rare case.
2. **Declined claims.** They're listed but not counted, matching the Claims Desk's own count, so the list can show more claims than the count. The note under the list says so.
3. **Which term.** The page shows the latest term, so the comparison uses that term's inception. Earlier terms aren't compared.
4. **Two HTTP calls per page load.** When the Claims Desk is down, each can wait up to 2 s.
5. **The flag is advice.** It says the premium "may be too low". Repricing, or changing Heron's count, is out of scope.

## Out of scope
Changing Heron's figure, comparing earlier terms, linking to Claims Desk screens, and the claim marker (`CLMCUR`).

Approved by Developer Name on 2026-11-17

## Proof

| AC | Test or check | Result |
|---|---|---|
| AC1 | `test_claims_history.py::test_policy_lists_claims_from_claims_desk` | pass |
| AC2 | `test_claims_history.py::test_flags_when_heron_count_is_lower` | pass |
| AC3 | `test_claims_history.py::test_no_flag_when_counts_agree` | pass |
| AC4 | `test_claims_history.py::test_policy_with_no_claims` | pass |
| AC5 | `test_claims_history.py::test_policy_loads_when_claims_desk_down` | pass |
| AC6 | Playwright check: `{"varrowstone":true,"noClaims":true}` | pass |
| AC7 | `(cd tests && uv run --project ../server pytest -q)`: 126 passed; `(cd client && npm run build)`: built | pass |
| AC8 | `git diff --name-only card-4`: only `server/modern/api.py` and `client/src/views/Policy.vue` | pass |
