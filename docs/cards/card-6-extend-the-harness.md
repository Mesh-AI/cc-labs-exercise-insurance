# Card 6: extend the harness

**Size:** open, an extension for anyone who has finished cards 1 to 5. **Connects to:** the harness itself (`CLAUDE.md`, `.claude/`), not the app.

## Today
The harness you built is deliberately minimal. It works because Claude follows instructions, not because anything forces it to:
- **Approval is text.** "Approved by …" is a line that Claude writes into a file. Nothing checks that you actually typed "I approve".
- **The gates are prose.** The skills say "don't build without an approved spec". Nothing stops an edit to `server/modern/api.py` when there's no spec at all.
- **The hook has gaps.** It guards Edit and Write. Does it stop `sed -i` or `cp` run through Bash?
- **The builder marks its own homework.** The same session that wrote the code also writes the Proof table.
- **It stops at build.** Nothing helps you review, commit, open a PR, or check approvals once the work leaves your laptop.
- **The repo's rules live in documents.** "Never import `server/systems/`" and "carry on when a system is down" are in `docs/ARCHITECTURE.md`, and no test checks either one.

## The change
Pick one weakness above, or one of your own, and make the harness better at it. Take the change through your own harness: `/intent`, `/spec`, `/build`. It's a change like any other, and the spec is where you decide how far to go.

There's no single right answer. A good result is small, does one thing you can demonstrate, and leaves the intent → spec → build flow as easy to use as before.

## Why
- **Instructions are probabilistic, checks are deterministic.** Knowing which rules belong in a prompt and which belong in a hook, test or CI job is most of what makes a harness trustworthy.
- **Your team will inherit it.** A harness that only works when everyone, Claude included, behaves won't survive contact with a real delivery team.
- **It's the same loop.** Building the harness with the harness shows you where the flow helps and where it gets in the way.

## Where to look
- `CLAUDE.md`, `.claude/skills/*/SKILL.md`, `.claude/settings.json` and `.claude/hooks/`: the harness you have now (or `git checkout harness` for a reference one)
- `docs/ARCHITECTURE.md`: the rules that are only written down today
- `intents/`: what your earlier cards produced, and therefore what a reviewer or a CI job would read
- Claude Code docs: [hooks](https://code.claude.com/docs/en/hooks), [subagents](https://code.claude.com/docs/en/sub-agents), [skills](https://code.claude.com/docs/en/skills), [GitHub Actions](https://code.claude.com/docs/en/github-actions). Or just ask Claude: "How do hooks work in Claude Code?"

## Done when
- You can demonstrate the improvement: show it blocking, catching or producing something the old harness didn't.
- Your intent and spec for the change are approved and in `intents/`.
- Card 1 to 5 work still goes through intent → spec → build with no extra friction, and every test still passes.

## A good spec will ask
What happens when it goes wrong? A gate that blocks too much gets switched off, and one that fails silently is worse than none. Say how someone gets past it legitimately, and what they see when it fires.

## Out of scope
Changing the app. If an idea needs an app change to prove it works, keep that change tiny and throw it away afterwards.

---

## Ideas, if you want them

Try to come up with your own first. Each idea below opens to show a starting prompt and a sketch. The sketches are untested starting points, not solutions: check them against the docs, and let your spec decide the details.

<details>
<summary><strong>1. Make approval tamper-proof</strong>: only a human can approve</summary>

**The idea.** Today Claude writes the approval line, so a confused or over-eager session could approve its own spec. Move that decision out of the model: record what you typed with a `UserPromptSubmit` hook, and block any write of `Approved by` unless your last message really was an approval.

**Prompt to start with**
> /intent I want approvals to be enforced by hooks rather than by instructions. Claude must not be able to write an "Approved by" line unless my most recent message explicitly approved that file.

**Sketch**

`.claude/settings.json` (add alongside the existing PreToolUse hook):
```json
"UserPromptSubmit": [
  { "hooks": [ { "type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/remember_prompt.py\"" } ] }
]
```

`.claude/hooks/remember_prompt.py`:
```python
import json, os, sys
prompt = json.load(sys.stdin).get("prompt", "")
state = os.path.join(os.environ["CLAUDE_PROJECT_DIR"], ".claude", "state")
os.makedirs(state, exist_ok=True)
open(os.path.join(state, "last-prompt.txt"), "w").write(prompt)
```

A PreToolUse check on Edit/Write:
```python
text = tool_input.get("new_string") or tool_input.get("content") or ""
if "Approved by" in text and not re.search(r"\b(i )?approve[d]?\b", last_prompt, re.I):
    print("Only the person at the keyboard can approve. Ask them.", file=sys.stderr)
    sys.exit(2)
```

**Things to decide in the spec:** does "approved, but change AC3" count? Should the hook write the approval line itself, with the date and `git config user.name`, so Claude never does? Add `.claude/state/` to `.gitignore`.
</details>

<details>
<summary><strong>2. Turn the gates into hard stops</strong>: no spec, no code</summary>

**The idea.** Block edits to application code (`server/modern/`, `client/src/`) unless there's an intent whose `spec.md` carries an approval line. Close the Bash gap in the protected-files hook while you're at it.

**Prompt to start with**
> /intent The build gate is only an instruction today. I want a hook that blocks edits to application code unless an approved spec exists for the change in progress. Also check whether the protected-file hook can be bypassed through Bash, and close the gap if so.

**Sketch**
```sh
# .claude/hooks/require_spec.sh, a PreToolUse hook on Edit|Write
path=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["tool_input"].get("file_path",""))')
case "$path" in
  */server/modern/*|*/client/src/*)
    grep -lq '^Approved by' "$CLAUDE_PROJECT_DIR"/intents/*/spec.md 2>/dev/null || {
      echo "No approved spec in intents/. Run /intent first." >&2; exit 2; } ;;
esac
```

**Things to decide in the spec:** "any approved spec" is weak. How do you know which intent is *active*: a pointer file, the branch name, or the newest folder? For Bash, matching `sed -i`, `>` and `cp` against protected paths will never be complete. Is a `Stop` hook that runs `git diff --name-only` and fails on protected paths more robust?
</details>

<details>
<summary><strong>3. An independent reviewer</strong>: the builder doesn't mark its own homework</summary>

**The idea.** Add a review stage, or end the build stage with one, that hands the diff and the spec to a subagent with a fresh context and read-only tools. It checks every AC against the code and tests, looks for changes the spec didn't ask for, and reports. You decide what to do with the findings.

**Prompt to start with**
> /intent After a build, I want an independent review: a read-only subagent that never saw the build conversation checks the diff against spec.md and reports, for each AC, whether the code and tests really prove it, plus anything changed that the spec didn't ask for.

**Sketch:** `.claude/agents/spec-reviewer.md`
```markdown
---
name: spec-reviewer
description: Reviews a finished build against its approved spec. Use after /build.
tools: Read, Grep, Glob, Bash
---
You are reviewing someone else's work. You did not write it.
1. Read intents/<slug>/spec.md and run `git diff main --stat` and `git diff main`.
2. For each AC: find the test or check, read it, and say whether it really
   proves the AC (not just that it passes). Run the tests.
3. List every changed file the spec's Design doesn't mention.
4. Report a table: AC | verdict (proven / weak / missing) | evidence (file:line).
Do not edit anything.
```

**Things to decide in the spec:** does a "weak" verdict block anything, or only inform? Should the reviewer use a different model? How do you stop it rubber-stamping, for example by asking it to name the weakest test?
</details>

<details>
<summary><strong>4. Make the architecture rules executable</strong></summary>

**The idea.** `docs/ARCHITECTURE.md` says: reach other systems over HTTP, never import `server/systems/`, and keep going when a system is down. Turn those into tests or a check that fails the build, so they hold whether or not anyone (or any model) read the document.

**Prompt to start with**
> /intent The rules in docs/ARCHITECTURE.md are only written down. I want them checked automatically: fail if code in server/modern imports server/systems, and prove each journey still works when a downstream system is unreachable.

**Sketch:** `tests/backend/test_architecture.py`
```python
import ast, pathlib

MODERN = pathlib.Path(__file__).parents[2] / "server" / "modern"

def test_modern_never_imports_downstream_systems():
    offenders = []
    for f in MODERN.rglob("*.py"):
        for node in ast.walk(ast.parse(f.read_text())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            offenders += [f"{f.name}: {n}" for n in names if n.startswith("systems")]
    assert not offenders, offenders
```

**Things to decide in the spec:** which other rules can be made executable (no hard-coded `localhost` URLs, every HTTP call has a timeout)? Should the build skill tell Claude to read the failures rather than the document?
</details>

<details>
<summary><strong>5. A ship stage</strong>: from approved build to reviewable PR</summary>

**The idea.** Add a fourth skill that creates a branch, commits, and opens a PR whose description is built from the intent, the spec's acceptance criteria and the Proof table. Optionally add a CI job that fails a PR when `intents/*/intent.md` or `spec.md` lacks an approval line, or when a protected file changed.

**Prompt to start with**
> /intent The harness stops at build. I want a /ship stage that commits the approved change on its own branch and opens a PR that a reviewer can judge without opening the chat: what was asked, the acceptance criteria and the proof. Also a CI check that rejects PRs with unapproved intents or specs.

**Sketch:** `.github/workflows/harness.yml`
```yaml
on: pull_request
jobs:
  approvals:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - name: Every changed intent and spec is approved
        run: |
          for f in $(git diff --name-only origin/${{ github.base_ref }} -- 'intents/*/intent.md' 'intents/*/spec.md'); do
            tail -n 20 "$f" | grep -q '^Approved by' || { echo "::error file=$f::not approved"; exit 1; }
          done
```

**Things to decide in the spec:** the Proof table sits *after* the approval line in spec.md, so "ends with an approval line" breaks. What exactly should CI check? Should the PR be a draft until a human has reviewed it? And should CI re-run the tests, rather than trust the Proof table?
</details>

<details>
<summary><strong>6. A domain expert at the spec stage</strong></summary>

**The idea.** Most of the good questions in cards 1 to 5 were domain questions: which date to compare at, whether tax is in the price, what a credit hold means for a quote. Give the spec stage an "underwriter" subagent that reads `docs/DOMAIN.md` and the draft spec, and raises the questions a senior underwriter would before you approve it.

**Prompt to start with**
> /intent Before I approve a spec, I want it challenged by a domain reviewer: a subagent that knows docs/DOMAIN.md and thinks like a senior commercial underwriter, and adds its questions to the spec's Areas of concern.

**Sketch:** `.claude/agents/underwriter.md`
```markdown
---
name: underwriter
description: Challenges a draft spec from a commercial insurance underwriter's point of view.
tools: Read, Grep, Glob
---
You are a senior commercial underwriter at Larkspur & Dene. Read docs/DOMAIN.md
and the spec you are given. Raise at most five questions where the spec could
price, bind or report something wrongly: dates, tax, terms, regulatory duties
(fair value, data), and what happens to customers in edge cases. Be specific
and cite the AC you mean. Don't comment on code style.
```

**Things to decide in the spec:** always run it, or only when the spec touches pricing? How do you test it? One way is to replay an earlier spec with its key concern removed and see whether the underwriter finds it.
</details>
