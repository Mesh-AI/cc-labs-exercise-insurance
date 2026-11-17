# CLAUDE.md

Larkspur & Dene policy modernisation workbench. Read README.md and docs/ARCHITECTURE.md for the layout.

## Every change goes intent → spec → build

1. `/intent` (or "let's start a change"): interview, write `intents/<slug>/intent.md`.
2. `/spec` (or "write the spec"): turn the approved intent into `intents/<slug>/spec.md`.
3. `/build` (or "build it"): implement the approved spec and prove every acceptance criterion.

## Approval rule

- A stage may start only when the previous file ends with an approval line:
  `Approved by <name> on <YYYY-MM-DD>`
- Only add that line when the person at the keyboard explicitly approves in chat ("approved", "I approve"). Silence, "looks good, but…", edits, questions or anything else are not approval.
- `<name>` comes from `git config user.name`. If it is empty, ask for the name and suggest `git config --global user.name "<name>"`.
- If an approved file changes, remove its approval line and ask again.

## Never change

- `server/legacy/` (Heron)
- `tests/backend/test_characterisation_*.py`
- `server/data/legacy/RATTBL.csv`

A hook blocks edits to these. If a test fails, fix the code, not the test.

## Commands

- Tests: `(cd tests && uv run --project ../server pytest -q)`
- Data integrity: `(cd server && uv run python ../scripts/check_data.py)`
- Run the app: `./scripts/start.sh` / `./scripts/stop.sh`
