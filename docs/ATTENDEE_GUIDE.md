# Attendee guide

One page for the afternoon. Johan walks through the same steps on the main screen, one step ahead of the room.

## Before the hands-on (14:25, 10 minutes)

1. Start the app: `./scripts/start.sh`, then open http://localhost:3000/dashboard/. Have a look at the quote screen and a policy page so you know what is there.
2. Check the tests pass: `cd tests && uv run --project ../server pytest -q`.
3. Build the harness: open Claude Code at the repo root and paste the prompt from [HARNESS_PROMPT.md](HARNESS_PROMPT.md). Answer its questions, review what it made, and commit it.

If the harness comes out wrong and time is short, `git checkout harness` gives you a working one.

## Each hands-on block (45 minutes)

| Minutes | Step | What you do |
|---|---|---|
| 2 | Choose | Pick a card from [cards](cards). Cards 1 and 2 for block 1 |
| 10 | Intent | Run `/intent`. Answer Claude's questions. Read `intent.md` and approve it |
| 10 | Spec | Run `/spec`. Read `spec.md`, especially Concerns. Push back, then approve |
| 20 | Build | Switch to auto mode and run `/build`. Let it work; review the result, not every step |
| 3 | Review | Check the diff against the spec, run the tests, commit intent, spec and code together |

If your first change runs long, finish it in block 2 rather than starting a second.

## The rules of this repo

- Never change `server/legacy/`. The characterisation tests prove Heron's prices are unchanged, and they must keep passing.
- Call underwriting, claims and finance over HTTP. Never import from `server/systems/`.
- If one of those systems is down, the journey must still work.
- `docs/ARCHITECTURE.md` and `docs/DOMAIN.md` have the details. Point Claude at them.

## Stuck?

- Ask an Indicium engineer. Their main job today is keeping changes small enough to finish.
- Ports in use: `./scripts/stop.sh`, then start again.
- Want to start the card again: `git stash` or `git checkout .` takes you back to your last commit.

## At 16:20

Fill in the [use case card](USE_CASE_CARD.md). Then show your intent, spec and diff to your own group.
