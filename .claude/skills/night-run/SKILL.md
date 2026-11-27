---
name: night-run
description: How one orchestrating agent runs an unattended night on the board. It writes and promotes cards, hands them to implementer agents, keeps a run log and writes the morning handover, and never builds, reviews or merges itself. Use this when you are told to orchestrate or lead a night run, when a scheduled check-in of a night run wakes you, and after a compaction during one.
---

# Running a night

You keep cards flowing. You write cards, promote them, hand them out, read short reports and keep the log. Implementers build, review and land. You never read a diff, run a test, fix code or merge. Every time you are tempted, write a card or hand the question to an agent.

`board` below means `python3 .claude/skills/scrum-board/board.py`. The T3 tools (`delegate_task`, `task_status`, `task_cancel`, `schedule_task`, `t3_thread_send`, `orchestrator_capabilities`) may load late: fetch them with ToolSearch.

## Where the truth lives

| What                    | Where               |
| ----------------------- | ------------------- |
| Cards, owners, progress | The board           |
| Plan, contracts, limits | The run issue       |
| Your own memory         | `logs/night-run.md` |

The run log sits in the main checkout and is ignored by git. Append one line after every start, report, decision and check-in: `HH:MM | event | card | task id | thread id | note`. Take the time from `date`, never from memory. You will be compacted during the night. Whatever is not in the log or on the board is gone.

## Start

1. Read the run issue in full. It names the cards, the contracts, the limits and the times.
2. Preflight, and log each result:
   - `date`.
   - `git status` in the main checkout: clean, on `main`, level with origin.
   - `board list` works.
   - `docker compose ps` shows Postgres up.
   - `.claude/skills/night-run/usage.sh` prints a number.
   - Free disk above 10 GB.
   - `caffeinate` is running.
   - `git ls-tree origin/main .claude/skills/build-card .claude/skills/land-card` lists both. Without them no implementer can work: stop and say so.
3. Call `orchestrator_capabilities` once.
4. Schedule the check-in: `schedule_task` with an interval of 20 minutes, bound to this thread, with the prompt "Night-run check-in: follow the wake steps of the night-run skill." Log its id.
5. Go to the wake steps.

## Wake steps

Run these on every wake: a finished child, a check-in, a compaction, a message.

1. `date`. Read the last 40 lines of the log. After a compaction, also read this skill and the run issue again. Then `git pull --ff-only` in the main checkout, so new children and your own `board` start from what has landed.
2. **Children:** for every task the log lists as running, call `task_status`. Believe that, not the log. A child that ended without a report counts as a failed attempt. Then run `board stale`: it lists started cards that have been silent for 90 minutes, yours and those of other runs. A stale card that is not in your log and is in your scope gets a fresh agent whose brief says "take the card over with `board claim <n> --agent <name> --takeover`". Log it with `SYSTEM`.
3. **Reports:** log each one in a line. Then:
   - Merged: nothing more to do.
   - Blocked by the implementer, or claim refused: log it. The card needs nothing more from you and the slot is free.
   - Failed once: start a second agent on the same card with the same agent name and effort `max`, and pass the first report along.
   - Failed twice: `board block <n> "<what a human has to decide>"` and leave the draft PR.
   - It names a problem with the board or a skill: see "Improving the system".
4. **Limits:** read the time and, at every check-in, the usage. Apply the limits from the run issue. Past the freeze time you start nothing new.
5. **Fill the free slots:** `board next --all` lists the cards that can start now. It has already left out every card whose `Owns` paths overlap a card In progress or In review, whoever runs it, and every card that overlaps one ahead of it in the list, so all listed cards can start together. Start one implementer per free slot, at most the number the run issue allows. Skip a card the log shows as running, even if the board still lists it. Under `Held back:` the command names why each other Ready card waits. A card that waits for one in Backlog or Blocked will not start tonight: log it once, and name it in the handover.
6. **Empty board, time left:** write the next cards from the plan, promote them, go to step 5. If the plan is used up, start the audit.
7. Log what you did. End your turn. A finished child or the next check-in wakes you.

## Handing out a card

`delegate_task` with `isolation: "worktree"`, `mode: "async"`, `role: "implementation"`, `target: {model: "<from the run issue>", options: {effort: "high"}}`, title `Card #<n> <title>`, and this task. Log the task id and the thread id it returns.

The agent name carries the number of your run issue, `r<run>-c<n>`. Another run on the same board then never passes for the owner of your card, even on a shared GitHub login. A second attempt keeps the name.

```
Use the build-card skill on card #<n> of this repo. Your agent name is r<run>-c<n>.
The run issue is #<run>: read its Contracts section before you write code.
<At most three lines of context the card does not hold, such as the report of a failed first attempt.>
Report as the skill says.
```

Nothing else. The card is the brief. If you feel the need to explain more, the card is incomplete: fix the card.

## Writing a card

```
board add --title "<what works afterwards>" --size S --priority P1 --body "## Why
<one or two sentences: who needs this and what for>

## What
<two to five lines: what gets built, where it lives, its limits as numbers, what is left out>

## Acceptance criteria
- [ ] <something a reviewer can check>

## Owns
<the paths this card may change>

## Check
<the command or the steps that prove it works>

## Demo-path step
<step of docs/demo-path.md, or none>

after #<n>"
```

- A card fits one agent for about an hour, review and landing included. Split anything larger into cards that each work end to end.
- `## What` names what gets built and where, with limits as numbers, and the criteria say what is true afterwards. Neither says how to code it. An agent that has never seen this conversation must be able to build it. `scrum-board` has the rules and an example under "Writing a card".
- Two cards that change the same lines get an `after #<n>` between them.
- Promote with `board move <n> ready` only what the run issue covers. That scope is the humans' decision, already taken. Anything else stays in Backlog for them.
- Read the acceptance criteria before you promote a card, your own included. A card that leaves a decision to a human, or holds a criterion no agent can check (such as a pass rate that changes from run to run), stays in Backlog: its agent would block it within minutes.
- A decision from a human that answers a Blocked card goes on the card with `board answer <n> "<the decision>"`. The card is then Ready for whoever is free. When the answer binds more than that card, also add it to #47 as `scrum-board` says under "Decisions".

## Several runs on one board

Other people may run their own orchestrators and agents on the same board tonight. The board is what you share; your log is yours alone.

- The slot limit of your run issue counts your own children only.
- A card In progress or In review that your log does not list belongs to another run. Leave it alone unless `board stale` lists it.
- A "claim refused" report means another run was faster. The slot is free; start the next card.
- Never answer, unblock or re-prioritise a card outside the scope of your run issue.

## Reviews and audits

Each implementer gets its own PR reviewed by a fresh reviewer; that is part of `build-card`. On top of that, when the first wave has landed and again before the freeze, start one audit agent (`role: "review"`, `isolation: "worktree"`):

```
Audit branch main of this repo. Change no code. First: git fetch origin,
git switch --detach origin/main, .claude/skills/build-card/worktree-env.sh 900. Read CLAUDE.md. Run .claude/skills/land-card/gates.sh. Start the app on the ports the script printed
and use every feature once, in light and dark. Report at most 15 lines: gates, what is broken,
where the tree breaks our rules (layers, features importing each other, hard-coded values,
missing states, missing docs). Add one Backlog card per real problem with
`board add --size S --priority <P0 to P2>`, its body under the headings ## Why,
## What, ## Acceptance criteria, ## Owns, ## Check and ## Demo-path step.
```

Promote the cards it adds if they are in scope.

## Improving the system

The board and these skills are part of what is being tested tonight. When an agent reports that a command failed, a card was unclear, two agents collided, a check was missing or a step cost time for nothing:

1. Log it with the word `SYSTEM`.
2. Write a card that fixes the cause in the skill, the script or `board.py`. Make it P0. One cause per card.
3. Hand it out like any other card.

Do not work around a problem twice. The second time it is a card.

## Limits and stops

- **Usage:** from `usage.sh`. Above the soft limit of the run issue, start nothing new. Above the hard limit, tell the running children to wrap up and go to the handover.
- **A child silent for 45 minutes:** `task_status`. If it is still working, leave it. If it stopped, treat it as a failed attempt.
- **main red** (an audit or an implementer reports failing gates on the head): start nothing else until one agent has fixed it. That fix is the only P0.
- **Network or GitHub down:** wait for the next check-in. Do not retry in a loop.
- **You do not know what is running:** stop starting things, read the log, check every task id.

## Freeze and handover

- **At the freeze time:** start no new card. Running cards may finish.
- **At the last-merge time:** send every running child one message with `t3_thread_send`: stop, push the branch, open or keep a draft PR, comment the state on the card, report. Nothing lands after that.
- **Handover:** post one comment on the run issue and append it to the log:
  - Landed: the cards and one line each on what now works.
  - Not landed: card, draft PR, what is missing.
  - Blocked: card and the question.
  - `main`: head commit and whether the gates pass (from the last audit).
  - Usage at start and at the end.
  - What the system got wrong and what changed tonight.
  - The first three things a human should do in the morning.
- Disable the check-in: `schedule_task` with its id and `enabled: false`. Then stop.

## Never

- Read diffs, run gates, fix code or land yourself.
- Touch `prod`, force-push a shared branch, or close someone's PR.
- Stop a process by name. Agents stop their own servers by port.
- Put a secret into a card, a brief or the log.
- Start more agents to make up for lost time. Fewer, smaller cards land more.
