# Architecture

Four systems, one process. They run on one port so the lab works the same in every sandbox, but treat them as four systems owned by four teams.

```
                         +--------------------------+
  Browser (port 3000)    |  New front end (Vue)     |
  /dashboard/            +------------+-------------+
                                      | /api/v1 via the Vite proxy
                         +------------v-------------+
                         |  New API  server/modern  |
                         |  api.py -> adapter.py    |
                         +------------+-------------+
                                      | Python calls (adapter only)
                         +------------v-------------+       overnight file
                         |  Heron    server/legacy  | - - - - - - - - - -> Finance
                         +--------------------------+
         over HTTP only  |              |              |
               +---------v--+   +-------v-----+   +----v--------+
               | Underwriting|  | Claims Desk |   | Finance     |
               | Workbench   |  |             |   | Ledger      |
               +-------------+  +-------------+   +-------------+
                 /api/systems/underwriting  /claims  /finance
```

## The rules that matter

- **Heron is the system of record.** It prices, refers and holds every policy. The new API never re-implements a rule: it calls Heron's own functions through `server/modern/adapter.py`, so prices match by construction.
- **Never change `server/legacy/`.** Changing a price is a decision for underwriting and finance. The characterisation tests in `tests/backend/test_characterisation_*.py` pin every rule to the penny.
- **Talk to the downstream systems over HTTP, never by importing `server/systems/`.** They belong to other teams. Read the base URL from `ESTATE_BASE_URL`, defaulting to `http://localhost:8001/api/systems`.
- **A downstream system being down must not break a journey.** Carry on with less and say so on screen.
- **The browser only calls relative `/api/...` paths.** Port 8001 is not reachable from the browser in the sandbox; Vite proxies `/api`.
- **The lab clock is frozen** at the date in `server/data/as_at.json` (12 November 2026), so every team gets the same answers.

## The new API, /api/v1 (server/modern/api.py)

| Method and path | What it does |
|---|---|
| `GET /lookups` | Products, trades, constructions, excesses, active brokers, lab date |
| `GET /insureds?q=` | Find an existing insured by name |
| `POST /quotes/price` | Price a risk without saving. Body: `risk`, optional `broker_code`, `insured_ref` |
| `POST /quotes` | Save a quote in Heron |
| `POST /quotes/{ref}/bind` | Bind a saved quote. Heron writes the NB transaction |
| `GET /policies?q=&status=` | Search policies |
| `GET /policies/{ref}` | One policy with transactions and endorsements |
| `POST /policies/{ref}/adjustments/preview` | Cost of a mid-term change, nothing saved |
| `POST /policies/{ref}/adjustments` | Apply a mid-term change |

## The downstream systems

Interactive docs for each are at `/api/systems/<name>/docs`. Money is in pounds, dates are ISO. `policy_ref` is Heron's policy number, `policy_term` its term number, `insured_ref` its insured number as a string.

**Underwriting Workbench** (`/api/systems/underwriting`)
- `POST /assessments`: appetite, technical price, accumulation and a decision for a risk. Pass `quoted_premium` to get `deviation_from_technical_pct`.
- `GET /referrals?policy_ref=`, `POST /referrals`, `POST /referrals/{ref}/decision`
- `GET /appetite`, `GET /accumulations`

**Claims Desk** (`/api/systems/claims`)
- `GET /experience?policy_ref=|insured_ref=&as_at=&term_start=`: `claims_count_3y`, open claims, paid, outstanding, incurred, and whether there is a claim in the current term
- `GET /claims?policy_ref=|insured_ref=`, `GET /claims/{ref}`, `POST /claims`

**Finance Ledger** (`/api/systems/finance`)
- `POST /postings`: post one premium transaction. Idempotent on `transaction_ref` (`HERON-` plus the seven digit transaction number). Rejects IPT that does not reconcile to 12%.
- `GET /ledger?policy_ref=`, `GET /policies/{ref}/balance`, `GET /brokers/{account}/statement` (`account` is `BRK-` plus the broker code; includes `policies_on_credit_hold` and `overdue_amount`), `POST /payments`

## Front end (client/src)

| File | What it is |
|---|---|
| `views/QuoteJourney.vue` | New business quote and bind, priced live |
| `views/Policies.vue`, `views/Policy.vue` | Policy search, policy page and mid-term adjustment |
| `views/DataHealth.vue` | The integrity checks |
| `components/PremiumSchedule.vue`, `components/DecisionBanner.vue` | The price breakdown and the accept or refer banner |
| `api.js` | Every backend call. Add new calls here |
| `styles/tokens.css` | Design tokens. Use them, never raw colours |
