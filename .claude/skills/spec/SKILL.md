---
name: spec
description: Stage 2 of a change. Use right after an intent.md is approved, or when the user asks for a spec (/spec, "write the spec"). Turns intents/<slug>/intent.md into spec.md with testable acceptance criteria.
---

# Spec

1. Check that `intents/<slug>/intent.md` ends with an `Approved by … on …` line. If it doesn't, stop and send the user back to the intent skill.
2. Read the code the change touches. Write `intents/<slug>/spec.md` with these sections:
   - **Summary**: one paragraph
   - **Design**: which files and endpoints change, and how. Never `server/legacy/`, the characterisation tests or `RATTBL.csv`.
   - **Acceptance criteria**: numbered AC1, AC2, … Each one must be checkable by a named test or command with a pass/fail result.
   - **Areas of concern**: risks, ambiguities, data or regulatory issues, anything the user must decide. Write "None" only if that's really true.
   - **Out of scope**
3. Show it and ask: "Do you approve this spec?" Revise until they explicitly approve. Anything other than explicit approval is not approval.
4. On approval, get the name from `git config user.name`. If it is empty, ask for their name and suggest `git config --global user.name "<name>"`. Append:
   `Approved by <name> on <YYYY-MM-DD>`
5. Ask: "Shall I start building? Switch to auto mode first (Shift+Tab)." Wait for a yes, then use the build skill.
