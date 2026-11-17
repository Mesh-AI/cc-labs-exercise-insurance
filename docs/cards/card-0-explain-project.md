# Card 0: get Claude to explain the codebase

**Size:** tiny, optional, before block 1. **Connects to:** nothing. It reads code and changes none.

## Today
You open an unfamiliar repo with four systems, a 20-year-old pricing engine and rules you can't see from the file names. Reading it file by file takes longer than the hands-on block. Without a picture of how it fits together, you can't judge an intent, push back on a spec or review a diff. Those three judgements are your job in the intent > spec > build loop.

## The change
Ask Claude to explain the codebase at the level you need, then check what it tells you. For example:

> I am new to this codebase. Explain it to me using text and diagrams in a format that I can consume in less than 5 minutes.

Then follow up on whatever is unclear:
- "Trace one quote being priced, from the screen to Heron, with file and function names."
- "Which rules must a change never break, and where are they written down?"
- "Which card touches which system, and what is carried by hand today?"
- "Explain it again for a non-developer," or "go one level deeper on the adapter."

## Why
- **You review, Claude builds.** In auto mode Claude writes the code in minutes. Your part is to accept or reject the intent, the spec and the result, and you can only do that well if you know how the parts connect.
- **It is fast and fits you.** Five minutes, at your level, in the form you take in best: a diagram, a walkthrough or a table.
- **It trains the habit the rest of the day needs: verify.** Claude can be confidently wrong. Checking its explanation against the code and docs is the same move as checking a build against its acceptance criteria.

## Where to look
- `README.md`, `docs/ARCHITECTURE.md`, `docs/DOMAIN.md`: the written ground truth. Point Claude at them and compare.
- `server/modern/adapter.py`: the layer that makes the new API give exactly Heron's prices.
- `client/src/views/QuoteJourney.vue` and `server/modern/api.py`: the quote journey most cards change.
- `docs/cards/`: what you will be changing next.

## Done when
- You can say, without looking, where a quote's price comes from, and why the new API never re-implements it.
- You can name the rules a change must not break: Heron is untouched, other systems are reached over HTTP only, and a journey works when a system is down.
- You checked at least two of Claude's claims against the code or docs, using the file and line it cites, and they held.
- You know which system your first card connects to.

## A good explanation will
Cite real files and functions you can open, separate what the docs say from what Claude inferred, and mention Heron's known bugs, which the tests pin deliberately and nobody should fix.

## Out of scope
Changing anything. This card doesn't go through `/intent`, `/spec` and `/build`, and has nothing to commit. If the explanation turns up something worth changing, that becomes a new intent.
