---
name: build-card
description: Takes one board card from claim to merged on main, in its own worktree with its own database and ports. Use this when you are told to build, implement or work on a card ("build card #14", "take the next card", "use build-card on #14"), when a night run hands you a card number, and when you resume a card you started earlier.
---

# Building a card

You own one card from claim to merged. Nobody is awake to answer questions, so pick the sensible default, keep going, and write every assumption into the PR body. You build exactly the card: what else you notice becomes a new card, never an extra change.

`board` below means `python3 .claude/skills/scrum-board/board.py`.

## 1. Claim

- You were given a card number and an agent name: `board claim <n> --agent <name>`.
- You were given nothing: `board next`, then claim that card under a name of your choice.
- You were told to take a silent card over: `board claim <n> --agent <name> --takeover`. It passes only for a started card with no activity for 90 minutes. Step 2 then finds its branch and PR: continue there.
- If the claim is refused, someone else has the card. Report "claim refused" with the reason in one line and stop.

## 2. Set up the worktree

Your worktree may start on a branch of its own, like `t3/card-<n>-implementation`. That branch is not an earlier attempt: build nothing on it, never push it, and leave it where it is.

First look for earlier work on this card: `git fetch origin`, then `gh pr list --state open --search "Closes #<n> in:body"` and `git branch -a --list "card-<n>-*" "origin/card-<n>-*"`. Only these count: the head branch of an open PR that closes the card, and branches named `card-<n>-...`, local or on origin.

- **Nothing there:** start fresh.
  ```
  git switch --no-track -c card-<n>-<two-or-three-words> origin/main
  .claude/skills/build-card/worktree-env.sh <n>
  ```
- **A branch exists:** continue on it with `git switch card-<n>-<words>`, then run `worktree-env.sh <n>`. If git says another worktree uses the branch, that attempt has ended, because only ended attempts are retried: `git worktree remove --force <its path>`, then switch.

The script starts a banking API of your own for this card, so your widgets, uploads and resets touch nobody else's data, creates two databases of your own (`trustroom_c<n>` and `trustroom_test_c<n>`), so your tests never empty another agent's tables, and writes `.env` in the worktree root with the model settings and your ports. It prints your ports. Use only those ports. Other servers on this machine belong to other agents and to the humans.

## 3. Read before you write

1. `board show <n>`: the card and its comments. Comments hold review feedback and earlier attempts.
2. The run issue, if you were given one: `gh issue view <run>`. Its Contracts section is fixed. Build against it. If your card cannot be built without changing a contract, comment on the run issue with the exact change and why, and go on with the smallest version that fits.
3. `CLAUDE.md`, and `starter/docs/` for anything that touches the e-banking (panel context, widgets, OCR).
4. The decisions list: `gh issue view 47`. A line that names your card, or the code your card touches, binds you. If your card can't follow it, block the card with the conflict.
5. The code your card touches, and one existing feature that already does something similar. Copy its shape.
6. What landed recently in the files you will touch: `git log --oneline -8 origin/main -- <paths>`.

## 4. Build

- Small commits, one per step that stands alone. One short plain line each. No co-author line and no mention of a tool or an AI, in commits or in the PR.
- Tests come with the code. When your card changes the behaviour an existing test pins, update that test and name it in the PR body with the reason. Never loosen, skip or delete a test to get a failing check past.
- The model cannot be trusted with exact values. A tool takes what the model knows (a name, a date) and resolves ids itself, with an error that says what to send instead.
- After you edit a shell script, or any file outside `src/`, look at `git diff --stat` and restore every line the card did not mean to change: a formatter hook may have rewritten the whole file.
- Secrets live in `.env` files only, which git ignores. Never print them, never put them in a card, a PR or a log.

## 5. Check your own work

Run `.claude/skills/land-card/gates.sh` as it is, never through a pipe such as `| tail`: a pipe returns the exit code of its last command and hides a failure. It has to pass before anything else. Its last line is `GATES PASSED` or `GATES FAILED: <gate>`. Push only after you have read `GATES PASSED`.

Then see it work, because passing tests are not proof:

- **Backend:** start your app on your port and call the new route or run one real turn with `curl`, against your own banking API.
- **Prompts or tools:** run the evals if the repo has them, against your own port. Add questions for your tool. One run is noisy: compare which questions fail with a run of `origin/main`, and do not land with new failures. Compare once, on the branch you send to review, against the `origin/main` of that moment. After a later rebase the gates are enough, unless the rebase had a conflict in a prompt file or tool description your card changes, or a review fix changed one: then compare again, against the new `origin/main`. Only one card at a time changes prompts or tool descriptions, because such an edit changes the answers to unrelated questions.
- **UI:** start your app, drive the page yourself with Playwright and system Chrome and look at the result, also at the 440 px width of the e-banking side panel. Check keyboard use, and the loading, error and empty states.

Stop your servers when you are done: `lsof -tiTCP:<port> -sTCP:LISTEN | xargs kill`. Remove your banking API and your databases after the card has landed: `docker rm -f trustroom-api-c<n>`, then `docker exec src-db-1 dropdb -U trustroom --if-exists trustroom_c<n>` and the same for `trustroom_test_c<n>`.

## 6. Open the PR and get it reviewed

```
git push -u origin HEAD
gh pr create --base main --title "<one line>" --body "<see below>"
```

Never push to `main` here, whatever a git hint suggests. That happens only in `land-card`.

The body holds one line on what now works, `Closes #<n>`, your assumptions, any red files you touched, and how you checked it. A card with an eval comparison names the commit of `main` it compared against.

A PR into `main` has one check: the Board workflow, which `gh pr checks` lists under its job name, `sync`. Look for `sync`, not `Board`. Wait for it with `.claude/skills/build-card/wait.py checks <pr>`, never with `sleep` (the harness blocks it). Run it with the Bash `timeout` at 600000 ms: it polls every 15 seconds and gives up after 9 minutes. Exit 0 means every check passed. Exit 1 means a check failed (it prints which, and `gh pr checks <pr>` links the log, so fix it and push) or `gh` failed (it prints the error). It also exits 1 within about 15 seconds when the PR conflicts with `main`, because a conflicting PR gets no run at all: it says so in one line, so rebase onto `origin/main`, push, and wait again. Exit 2 means the checks still run after 9 minutes: comment that on the card, then go on with the review.

Then run the `hackathon-review` skill. It starts a reviewer that has not seen your reasoning. Tell that reviewer to diff against `origin/main`. Fix blockers, at most two rounds.

## 7. Land

Follow the `land-card` skill. You are done when the PR shows as merged and the card is in Done.

## 8. Report

At most 10 lines, followed by the review block from `hackathon-review`: card, PR URL, merged or not, the head commit of `main`, what now works, what you could not verify, new cards you added, and anything about the board or these skills that slowed you down. That last point matters: the orchestrator turns it into a fix.

## When you are stuck

- **A check fails and you know why:** fix it.
- **A check fails after two honest attempts:** push the branch, open the PR as a draft, comment on the card with what you tried and what you saw, and report. Do not weaken the check.
- **You need a decision, a secret or a product choice:** `board block <n> "<question a human answers in one line>"`, then report.
- **Another agent's change broke yours:** read their card and PR, adapt, and say so in a comment on their card. Do not edit their branch.

## Never

- Push to `prod`, or force-push `main`.
- Stop a process by name. Stop it by its port.
- Wait for an answer. Ask on the card and move on.
- Build something the card does not ask for.
