# Larkspur & Dene: policy modernisation workbench

The practice repo for **Claude Code for Insurance**. Use it if you can't bring your own codebase.

Larkspur & Dene is a made-up commercial insurer. Its policy admin system, Heron, has priced every policy since 2004. A new front end and API now sit on top of Heron and give exactly its answers. The underwriting, claims and finance systems each still run on their own, and people carry the data between them. Each change card connects one of them.

Everything is synthetic. Company names are invented and every postcode uses letters Royal Mail never issues, so nothing here is real.

## Quick start

You need Python 3.11+, [uv](https://docs.astral.sh/uv/), Node 18+, git and Claude Code.

```bash
./scripts/start.sh
```

| What | Where |
|---|---|
| New front end | http://localhost:3000/dashboard/ |
| Heron legacy screens | http://localhost:3000/api/legacy/ |
| Backend API docs | http://localhost:8001/docs |
| Underwriting, claims and finance API docs | http://localhost:8001/api/systems/underwriting/docs (and `/claims/docs`, `/finance/docs`) |

```bash
cd tests && uv run --project ../server pytest          # all tests, about 3 seconds
cd server && uv run python ../scripts/check_data.py    # data integrity across the four systems
./scripts/stop.sh
```

## On the day

1. Build a simple harness with the prompt in [docs/HARNESS_PROMPT.md](docs/HARNESS_PROMPT.md).
2. Pick a change card from [docs/cards](docs/cards). Cards 1 and 2 suit the first block.
3. Take it from intent, to spec, to working code built by Claude in auto mode.
4. Fill in the [use case card](docs/USE_CASE_CARD.md).

The step-by-step is in [docs/ATTENDEE_GUIDE.md](docs/ATTENDEE_GUIDE.md).

## Layout

```
server/
  legacy/        Heron: the legacy engine and its screens. Do not change.
  systems/       Underwriting, claims and finance: mock downstream systems.
  modern/        The new API (api.py) and its adapter over Heron (adapter.py).
  data/          The synthetic book across all four systems, frozen at 12 November 2026.
  data_health.py Integrity checks across the four systems.
  main.py        One process on port 8001 hosting all of the above.
client/          The new front end: Vue 3 and Vite on port 3000.
tests/backend/   Smoke tests and characterisation tests that pin Heron's rules to the penny.
docs/            Architecture, domain, the cards and the attendee guide.
scripts/         start.sh, stop.sh and check_data.py.
```

## Branches

| Branch | What it holds |
|---|---|
| `main` | The starting point. No harness: you build it on the day. |
| `harness` | A finished reference harness, for anyone whose generation goes wrong. |
| `card-1` to `card-5` | The harness plus a finished intent, spec and build for that card. |

If you fall behind, `git checkout harness` gives you a working harness and you carry on from there.
