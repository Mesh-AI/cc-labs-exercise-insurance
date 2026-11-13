# Domain notes

## Words you will meet

| Term | Meaning here |
|---|---|
| Commercial property (CP) | Cover for buildings, contents and business interruption (BI) |
| Combined liability (CL) | Employers' and public liability, rated on employees and turnover |
| Sum insured | The most the policy pays for that section, in whole pounds |
| Premium | The annual price. Heron holds it in pence |
| IPT | Insurance Premium Tax, 12% on top of the premium |
| Commission | The broker's share of the premium, a percentage per broker |
| Quote, bind | A quote is a price that has been saved. Binding makes it a live policy |
| MTA | Mid-term adjustment: a change during the policy year, charged or refunded pro rata |
| Endorsement | The record of a change to a policy |
| Renewal, term | Each policy year is a term. Renewal writes the next term |
| Referral | A risk outside branch authority, waiting for an underwriter |
| Technical price | Underwriting's own view of what a risk should cost |
| Accumulation | Total sum insured in one postcode district, against a limit |
| Credit hold | A broker owes premium more than 60 days old |

## How Heron stores things

Dates are integers `CCYYMMDD`, premiums integer pence, sums insured whole pounds, percentages times 100 (`2250` is 22.5%), postcodes upper case with no space. Statuses: `Q` quote, `L` live, `R` renewed, `X` cancelled, `E` expired, `D` declined or not taken up. The adapter turns all of this into pounds, ISO dates and plain names.

## Data people carry by hand today

- **Claim count (`CLMCNT3`).** Branch staff copy it from the Claims Desk at quote and renewal. It drifts, and the price is based on whatever was typed.
- **Claim marker (`CLMCUR`).** Copied by hand. Cancellation refunds depend on it.
- **Referrals.** Re-keyed into the Underwriting Workbench. Heron's authority to bind is a hard-coded list of user names.
- **Premium.** Reaches finance in an overnight file.

The Data health page lists the policies where the copied fields are out of date.

## Known legacy behaviours

Pinned by the characterisation tests as they behave today. Do not fix them in code: a price change needs underwriting and finance sign-off. A spec that touches them should say so and name who must approve.

1. **Single-letter postcode areas never get their loading.** Heron holds loadings for L, M, E, B and G, but looks up the first two characters of the postcode, so Liverpool, Manchester, east London, Birmingham and Glasgow are priced with no area loading. The Underwriting Workbench does apply them, so these quotes come out roughly 7% to 15% below technical.
2. **IPT drops fractions of a penny** rather than rounding.
3. **Pro rata always divides by 365.** A term containing 29 February is charged 366/365 of the annual difference.
4. **Cooling-off refunds keep 50.00, not 25.00.** The 25.00 fee is applied, then the 50.00 minimum retained premium overrides it.
