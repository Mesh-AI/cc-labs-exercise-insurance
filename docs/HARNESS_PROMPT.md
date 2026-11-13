# Harness prompt

Run this in Claude Code at the root of the repo you are working on, your own or this one. It builds a small harness: a `CLAUDE.md`, two templates and three slash commands that walk you from intent, to spec, to code built in auto mode.

Johan will share the final version on the day. This draft is here so the repo is complete if you work through it on your own.

```
Set up this repository so every change goes through two written steps
before any code: an intent, then a spec. This is the common pattern in
spec-driven development: intent, then decomposition.

First explore the repo: its layout, how to run it, how to run the tests,
and any docs. Then ask me up to three short questions, such as what must
never be changed and who approves a spec.

Then create, keeping every file short:

1. CLAUDE.md: what the project is, the commands to start it and run the
   tests, its rules, and links to any docs folder. Add a short section on
   the intent > spec > build flow.

2. docs/sdlc/templates/intent.md: the problem, who it is for, what done
   looks like, what is out of scope.

3. docs/sdlc/templates/spec.md: the change broken into small steps, each
   with the test that proves it; what happens when something it depends
   on fails; and a "Concerns" section that asks whether the change
   touches pricing, a customer outcome or regulatory reporting, and who
   must sign it off.

4. Three slash commands in .claude/commands:
   /intent  interview me, then write specs/<slug>/intent.md from the template
   /spec    read an approved intent and write specs/<slug>/spec.md
   /build   implement an approved spec, run the tests until they pass,
            then summarise the diff against the spec
   Each one stops and asks me to approve before the next stage.

5. .claude/settings.json with two hooks: one that blocks edits to the
   paths I say must never change, and one that runs the tests after
   Python files are edited.

Do not change any application code. When you finish, list what you made
and tell me how to start.
```

On this repo, the answers to its questions are: never change `server/legacy/`, the characterisation tests, or `server/data/legacy/RATTBL.csv`; specs are approved by the person at the keyboard; and the tests run with `cd tests && uv run --project ../server pytest -q`.
