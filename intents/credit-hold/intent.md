# Intent: credit hold warning (card 4)

## What
- When a quote is priced for a chosen broker, the screen warns if that broker has any policy on credit hold (premium unpaid for more than 60 days). It shows the number of policies and the overdue amount.
- A broker in good standing, or one with no ledger history yet, shows no warning.
- The warning is advisory only: saving and binding are unchanged.
- If the Finance Ledger isn't answering, quoting still works and the screen says: "Finance Ledger not reachable: broker credit status not checked."

## Why
- Today a quote can be saved and bound for a broker who has owed premium for months, and credit control only finds out later. Broker B004 (Ivern Insurance Services) pays late. Most brokers, such as B001, are in good standing.
- A warning at quote time lets the clerk check with credit control before taking on more business through a broker in arrears.

## Constraints
- Don't change `server/legacy/`, the characterisation tests or `server/data/legacy/RATTBL.csv`.
- Call the Finance Ledger over HTTP only (`ESTATE_BASE_URL`), never by importing `server/systems/`.
- The check runs in `price_quote`, which already receives `broker_code`. The 60-day rule is the ledger's.
- If the ledger is down, the quote journey must not break.
- New tests must prove the warning and amount for B004, nothing for B001, no warning for a broker without ledger history, an unchanged price and decision, and pricing with the ledger down. All existing tests must still pass.
- Out of scope: blocking the save or bind, and chasing payment.

## Open questions (for the spec)
1. Warn or block? This change only warns. Blocking a broker is a credit control decision for the Head of Credit Control to sign off.
2. Which amount should be shown? The overdue amount (policies on hold only) can be higher than the broker's net outstanding when other policies are in credit. Credit control should confirm the overdue figure is the right one.

Approved by Developer Name on 2026-11-17
