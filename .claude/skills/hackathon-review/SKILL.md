---
name: hackathon-review
description: Self-review procedure an agent runs on its own changes before reporting a task as done or opening a PR. It checks the diff against our project rules (layers, async, LLM provenance, REST, frontend, tests, demo path, security, over-engineering) in a fresh subagent. Use this whenever you've finished a coding task in this repo, are about to open a PR or say "done", or the user asks to "review", "check" or "look over" changes, even if they don't say "review".
---

# Hackathon self-review

You've finished a change. Before you report it as done, get it reviewed by a reviewer that hasn't seen how you wrote it. Reviewing your own work in the same context mostly confirms your own decisions, so the review has to run in a fresh subagent.

This review checks **our rules and hackathon priorities**: what CI can't lint. It is not a generic bug hunt (that's `/code-review`), and it doesn't comment on style that ruff, ESLint or Prettier already enforce.

## 1. Make sure CI-level checks pass first

Run `.claude/skills/land-card/gates.sh`. Fix failures before reviewing; there's no point reviewing code that doesn't pass lint, types or tests.

## 2. Spawn the reviewer

Start a subagent with only this context. Replace `<base>` with the branch the PR targets, for example `origin/main`. Don't pass your reasoning or a summary of what you intended; the reviewer judges the code, not your intent.

> Review this diff for a hackathon project. Read `CLAUDE.md`, the body of issue #47 (`gh issue view 47`, the decisions that bind more than one card), `docs/demo-path.md` (if it exists) and `.claude/skills/hackathon-review/checklist.md`, then review the output of `git diff <base>...HEAD` (plus uncommitted changes from `git diff`) against the checklist. Report findings in the format the checklist specifies. Only report problems inside the diff.

## 3. Act on the findings

- **Blockers:** fix them, rerun the checks, then run the review once more in a *new* subagent.
- **Notes:** don't fix them unless they're trivial; put them in your report.
- **At most 2 review rounds.** If blockers remain after round 2, stop and report them. Don't loop. If you disagree with a blocker (e.g. you believe the rule doesn't apply), don't silently ignore it: say so in the report with your reasoning.

## 4. Report

End your task report with:

```
Review: <passed | N blockers open> (round <1|2>)
Blockers fixed: <short list, or "none">
Open blockers: <list with reasoning, or "none">
Notes: <list, or "none">
Demo path touched: <yes: which step | no>
```

Keep it short. People read this summary instead of the code.
