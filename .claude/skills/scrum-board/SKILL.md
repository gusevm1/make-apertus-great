---
name: scrum-board
description: How an agent works through the GitHub project board, our single source of truth for what gets built, who is on it and how far it is. Use this before starting any work in this repo ("what should I do next", "pick up a task", "work on #12", an unattended run), whenever you are stuck or need a decision, when you notice work outside your card, and when you finish. Also use it when someone asks what is in progress, blocked or done.
---

# Working through the board

The board is the single source of truth. What to build, who is building it and how far it is are read from the board, never from chat, memory or a label. If the board and anything else disagree, the board wins; if the board is wrong, fix the board.

Everything goes through one script, here called `board`:

```
python3 .claude/skills/scrum-board/board.py <command>
```

It needs the `project` scope once per machine: `gh auth refresh -s project`.

## The columns and who moves a card

| Status | Meaning | Moved there by |
|---|---|---|
| Backlog | An idea. Not agreed, maybe not refined. | Anyone who adds a card |
| Ready | Committed to this sprint. | Humans at the boundary |
| | Or: the PR needs rework. | CI: changes requested |
| | | CI: PR closed unmerged |
| In progress | Claimed, being built. | You, with `board claim` |
| | | CI: draft PR |
| In review | A PR with `Closes #<n>` is open. | CI: PR opened or pushed |
| Blocked | Needs a human answer. | You, with `board block` |
| | Stays there under a draft or closed PR. | |
| Done | The PR is merged. | CI, which also closes the issue |

CI here is the Board workflow, the only check on a PR into `main`. `gh pr checks` lists it as `sync`, its job name. You move cards only with `claim` and `block`. CI moves the rest from what GitHub can prove, so opening the PR correctly *is* how you report progress. Never move a card to In review or Done yourself. The one exception is step 6 of `land-card`, when CI did not move a merged card.

A card back in Ready with review comments is rework, not a new commitment. Its owner claims it again (same `--agent`), reads the comments and pushes to the same PR. A card closed as not planned is archived, never Done.

## The loop

0. **Resume:** after a restart, run `board list --mine --status in-progress`. `board claim <n>` passes for a card that is already yours, so carry on with it.
1. **Pick:** `board next` gives you the highest-priority Ready card that is yours or unassigned, isn't waiting on another card, and whose `Owns` paths don't overlap a card that anyone has In progress or In review. If it says there is none, stop. Don't take work from Backlog and don't invent work. Under `Held back:` it names the reason for every Ready card it did not offer: `waits for #<n> (<status>)`, `overlaps #<n> on <path>` or `assigned to <login>`. A card that waits for one in Backlog or Blocked waits until a human acts, so say so when you report.
2. **Claim:** `board claim <n>`. If it refuses (someone else got it), run `board next` again. No claim, no code.
   When several agents share one GitHub login, always pass `--agent <your name>`. It posts `Claimed by <name>`, and a card that is In progress or In review passes only for the agent named last.
3. **Read:** `board show <n>` prints the card and all its comments. The comments are the conversation: earlier attempts, review feedback, human answers. If the card already has an open PR (`gh pr list --search "Closes #<n> in:body"`), continue on that branch instead of starting over.
4. **Build** exactly the acceptance criteria, following CLAUDE.md. One card, one branch, one PR.
5. **Finish:** open the PR with `Closes #<n>` in the body (CI rejects a PR that links no card, or a card still in Backlog). List your assumptions in the PR body. Then go back to step 1.

## When you are stuck

If you need a decision, a secret, a 🔴 file or the criteria contradict each other: `board block <n> "<the exact question, and what you tried>"`. Write the question so a human can answer it in one line without opening the code. Then take the next card; don't wait.

A human, or an agent passing on a human's decision, answers with `board answer <n> "<the answer>"`. That posts the answer, clears the assignees and moves the card to Ready, so it comes up in `board next` for whoever is free. The agent that takes it finds the branch and the draft PR of the first attempt and continues there.

## When a card has gone silent

An agent can die with its card In progress or In review. `board stale` lists every started card with no comment, claim or push to its PR for 90 minutes, with the agent that claimed it last. Only such a card may change hands: `board claim <n> --agent <name> --takeover`. It refuses a card that was active more recently. After a takeover, continue on the card's branch and PR, never start over. The earlier agent, if it is still alive, is stopped by `land-card`, which checks the claim before it pushes.

## When you find other work

A bug, a follow-up, a missing piece: don't do it inside your card. Add a card and carry on:

```
board add --title "<what works afterwards>" --size S --priority P1 --body "## Why
<one or two sentences: who needs this and what for>

## What
<two to five lines: what gets built, where it lives, its limits as numbers, what is left out>

## Acceptance criteria
- [ ] <checkable>

## Owns
<the paths this card may change>

## Check
<the command or the steps that prove it works>

## Demo-path step
<step of docs/demo-path.md, or none>

after #<n>"
```

Sizes are `S` and `M`, priorities `P0` to `P2`. A missing heading, a missing `--size` or `--priority`, or a value the board doesn't have stops `board add` before it creates anything. The message names what is missing: fix it and run it again.

It lands in Backlog. The humans decide at the next boundary whether it gets built. `after #<n>` in the body keeps a card out of `board next` until card n is Done.

## Writing a card

Two readers use a card. The agent that builds it reads it first. Later, people open it to see what was built.

- **Title.** What works afterwards, with the thing named. "Attach a document to a question", not "Documents".
- **Why.** Who needs it and what for, in one or two sentences.
- **What.** Two to five lines on what gets built. Name the endpoint, the tool, the table or the part of the page. Give limits as numbers. Say what is left out. Describe behaviour and place, not how to code it.
- **Acceptance criteria.** Each one is something a reviewer can check.
- **Owns.** The paths the card changes. A card names its own test files, such as `src/backend/tests/test_documents.py`, never the whole `src/backend/tests/`: `board next` would hold back every other card that adds a test, so `board add` refuses it.

An example of What:

```
## What
`POST /api/documents` reads the file once with the OCR service and stores its text.
A message takes up to three document ids. Files over 10 MB are refused.
The chat shows the names of the attached files. It shows no preview of them.
```

Keep the whole card under about 25 lines and apply the `unslop` skill to it. A sentence that would fit any card says nothing about this one, so cut it. When a card lands, `land-card` adds an `## Implemented` comment, so the card also records what was built.

## Talking to other agents and to humans

The card is the channel. Anything another agent or a human needs to know (an assumption, a contract you changed, a hand-over) goes in a comment on the card it concerns: `gh issue comment <n> --body "..."`. Don't edit someone else's branch and don't rewrite someone else's card.

## Decisions

Issue #47, labelled `decisions` and pinned, lists the decisions that bind more than one card. Its body is the list of those that still hold, one line each. Its comments say why.

Add one when a choice reaches beyond your card: a contract other cards build on, the order cards must land in, an exception to a rule, or a human's answer that settles more than the card it was asked on. A choice only your card sees stays in your PR's assumptions.

1. Comment on #47:
   ```
   ## <the decision in one sentence>
   **Why:** <one or two sentences>
   **Instead of:** <the alternative that lost>
   **Cards:** #.., PR #..
   **Decided:** <date>, <by whom or on which card>
   ```
2. Read the body again, add `- <decision> (#cards) <comment url>` under `## Live`, and save it with `gh issue edit 47 --body-file <file>`.

To replace a decision, comment the new one, swap its line in the body, and change the first line of the old comment to `Superseded by <url>`. Never delete a comment.

Two agents editing the body at once can lose a line. The comment is the record, so the sprint boundary puts a lost line back.

## What you never do

- Move a card from Backlog to Ready, or change Priority or Sprint. That is the humans' sprint commitment. The one exception: a human in your session tells you to work on something now. Then add the card if it doesn't exist, `board move <n> ready`, and claim it.
- Assign anyone but yourself, or close an issue by hand.
- Work on a card that someone else claimed, unless `board claim --takeover` passed for it.

## Other commands

`board list` (all cards; `--status blocked`, `--mine`, `--json`), `board next --all` (every Ready card that can start now, in pick order, for an orchestrator handing out cards; no two of them overlap, so all of them can start together), `board stale` (started cards that went silent), `board answer <n> "<text>"` (answer a Blocked card), `board set <n> --size S`, `board move <n> <status>` (humans and the sprint-boundary skill).
