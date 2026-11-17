---
name: intent
description: Stage 1 of a change. Use when the user wants to start a new change, feature, fix or card ("new change", "I want to…", "let's do card 2", /intent). Interviews the user and writes intents/<slug>/intent.md.
---

# Intent

1. Interview the user, a few questions at a time, until you can state:
   - **What** is wanted (the outcome, not the solution)
   - **Why** (who benefits, what problem it solves)
   - **Constraints** (systems touched, things that must not change, deadlines, data rules)
   - **Open questions** you still have
   Read the relevant code and docs/ first so your questions are specific. Don't invent answers.
2. Pick a short kebab-case slug and write `intents/<slug>/intent.md` with those four sections. Keep it under a page.
3. Show it and ask: "Do you approve this intent?" Revise until they explicitly approve. Anything other than explicit approval is not approval.
4. On approval, get the name from `git config user.name`. If it is empty, ask for their name and suggest `git config --global user.name "<name>"`. Append:
   `Approved by <name> on <YYYY-MM-DD>`
5. Go straight on to the spec skill without waiting to be asked.
