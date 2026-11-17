---
name: build
description: Stage 3 of a change. Use when the user says yes to building an approved spec (/build, "build it", "go"). Implements intents/<slug>/spec.md and proves every acceptance criterion.
---

# Build

1. Check that both `intent.md` and `spec.md` in `intents/<slug>/` end with an `Approved by … on …` line. If either doesn't, stop and say which one.
2. If the user hasn't said yes to building yet, ask, and remind them to switch to auto mode (Shift+Tab). Once they say yes, work without further prompting.
3. Implement the spec. For each acceptance criterion, write or reuse a test or check that proves it. Put new tests in `tests/backend/`, never in the characterisation tests.
4. Run `(cd tests && uv run --project ../server pytest -q)` and the AC-specific checks. If something fails, fix the code, not the test. Repeat until everything passes.
5. Append a `## Proof` section to spec.md with a table: AC, test or command, result (pass). Every AC must be there.
6. Report what changed, then the proof table. Don't commit unless asked.
