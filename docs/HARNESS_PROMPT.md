# Harness prompt

Run this in Claude Code at the root of the repo you are working on, your own or this one. It builds a minimal harness, based on [the AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook), that takes every change from intent, to spec, to a verified build.

```
Read https://claude.com/resources/articles/the-ai-native-sdlc-playbook,
then set up a minimal harness in this repo that follows it. Explore the
repo first and ask me what you need to know.

Every change should go through three stages, each guided by a skill I
can trigger in plain words or as a slash command:

1. Intent: interview me and write intent.md: what is wanted, why, and
   under which constraints.
2. Spec: as soon as I approve intent.md, go straight on and turn it
   into spec.md, with testable acceptance criteria and any areas of
   concern flagged.
3. Build: once I approve spec.md, ask me whether to start building, and
   remind me to switch to auto mode first. When I say yes, implement it
   without further prompting and prove each acceptance criterion with a
   test or check that passes.

I must approve intent.md and spec.md before the next stage can start.
Never treat anything other than my explicit approval as approval.
Record each approval in the file with my name and the date. Take the
name from git config user.name. If that is not set, ask me for my name
and suggest I run git config --global user.name "<name>".

Keep everything as small as possible and do not change application
code.
```

On this repo, useful answers to its questions are: never change `server/legacy/`, the characterisation tests, or `server/data/legacy/RATTBL.csv`; specs are approved by the person at the keyboard; and the tests run with `cd tests && uv run --project ../server pytest -q`.
