# Attendee guide

## Intro to Spec Driven Development and the 2 Paths for the Hands-on

1. Why work by spec (5 mins Presentation): why specs lift us above vibe coding, and why they are kept in the repo as the record of who asked for what.
1. Intent-to-spec workflows (5 mins Presentation): the two steps every major spec-driven framework shares, intent and decomposition. [Anthropic's AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook) is shown as one example of the pattern, including where it is a good fit and where potentially less so.
1. The 2 Paths for the hands-on: BYO repo, or using this sample repo, and how to set up for each
    * Sanbox setup for this sample repo, including starting Claude and VSCode
    * Using your own repo, making sure that you are on a suitable branch, and starting Claude and your IDE


## Pre hands-on (10 minutes)

1. Start the app: `./scripts/start.sh`, then open http://localhost:3000/dashboard/. Have a look at the quote screen and a policy page so you know what is there.
2. Check the tests pass: `cd tests && uv run --project ../server pytest -q`.
3. Build the harness: open Claude Code at the repo root and paste the prompt from [HARNESS_PROMPT.md](HARNESS_PROMPT.md). Answer its questions, review what it made, and commit it.

If the harness comes out wrong and/or time is short, `git checkout harness` gives you a working one.

## Each hands-on block (45 minutes)

| Step | What you do |
|---|---|
| Choose | Pick a card from [cards](cards). Cards 1 and 2 are recommended for block 1 |
| Intent | Start a bit of work by either telling Claude in plain language ("Start work on Card 1") or by running `/intent`. Answer Claude's questions. **Read** `intent.md` and approve it |
| Spec | The harness will giude you through the spec phase as soon as the intent if approved, and make a spec for you. Read `spec.md`, especially Concerns. Push back, iterate, then approve |
| Build | Switch to auto mode and tell Claude to build. Let it work; review the result, not every step (unless you are interested) |
| Review | Check the diff against the spec, run the tests, check the results in the app |
| Document | Fill in the [use case card](USE_CASE_CARD.md). Then show your intent, spec and diff to your own group |

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


