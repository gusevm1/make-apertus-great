---
name: sprint-boundary
description: Runs the sprint boundary with the humans, review, retro and planning in one 10 to 15 minute meeting, from the board. Use this when someone says "sprint boundary", "standup", "sprint review", "retro", "plan the next sprint", "what did we get done" or asks for a status of the whole board.
---

# Sprint boundary

Every few hours the humans meet for 10 to 15 minutes. You prepare the meeting from the board, they decide, you write the decisions back to the board. Between boundaries the agents work alone, so whatever isn't on the board after this meeting doesn't exist for them.

You propose; the humans decide. Don't move, assign or re-prioritise anything before they have said yes.

Board commands are `python3 .claude/skills/scrum-board/board.py <command>`, here `board`.

## 1. Review: what happened

Get the facts with `board list --json`, `gh pr list --state all --json number,title,state,mergedAt,isDraft,statusCheckRollup,body` and, for Blocked cards, `board show <n>`. Then show the humans, shortest first:

- **Done** this sprint: card, one line on what now works, demo-path step.
- **Blocked:** card and the exact question. These get answered in the meeting, first, because every one of them is an idle agent.
- **In review:** card, PR, whether checks are green, how long it has waited.
- **In progress:** card, owner. Flag every card `board stale` lists: no activity on the card or its PR for 90 minutes. Flag a card with two assignees: two agents claimed it.
- **Ready but untouched:** card. Say why: `board next --all` names the reason under `Held back:`.

Then one line: is `docs/demo-path.md` working end to end right now? If you can't tell from the smoke tests, say that instead of guessing.

## 2. Retro: what to change

Look for what repeated: the same review blocker in several PRs, the same question in several Blocked cards, cards that came back from review, cards that were too large. Propose at most three changes, each as a concrete edit to `CLAUDE.md` or a skill, because that is the only way the agents will work differently next sprint. Ask the humans for theirs. Each accepted change becomes a P0 card. A line on the decisions list (#47) that every card has to follow is a rule: propose it as an edit to `CLAUDE.md`.

## 3. Planning: the next sprint

- Capacity is what actually got Done last sprint (count S as 1, M as 2), not what was hoped for. For the first sprint, assume one M per person.
- Propose cards from Backlog in priority order until capacity is full, demo-path steps first. A card without checkable acceptance criteria isn't a candidate: run `refine-issue` on it and offer it next time.
- Unfinished cards stay; they count against capacity.
- Say what you are leaving out and why. Close to the demo, propose what to cut.

The humans reorder, add, remove and say who owns what.

## 4. Write the decisions to the board

Only after a human has confirmed the list:

- Answers to Blocked cards: `board answer <n> "<the answer>"`. It posts the answer, clears the assignees and moves the card to Ready.
- Each committed card: `board set <n> --sprint S<k> --priority P<x>`, `board move <n> ready`, and `gh issue edit <n> --add-assignee <login>` for the owner the humans named. A card left unassigned is taken by whichever agent is free.
- Retro changes and new ideas from the meeting: `board add ...`.
- Decisions from the meeting that bind more than one card: add them to #47 as the `scrum-board` skill says under "Decisions".
- Prune #47. Put back the line of every comment that lost its line. Remove the line of a decision whose cards are all Done when no open card depends on it, and the line of one that is now in `CLAUDE.md`. The comments stay. Keep the list under 30 lines: a longer list means rules are waiting to move to `CLAUDE.md`.

## 5. Post the sprint log

One comment per boundary on the issue labelled `sprint-log` (find it with `gh issue list --label sprint-log`; if there is none, create it: `gh issue create --title "Sprint log" --label sprint-log --body "One comment per sprint boundary."`):

```
## S<k> → S<k+1>, <weekday HH:MM>
**Done:** #.. <what works now>
**Carried over:** #..
**Decisions:** <answers given, scope cut, retro changes>
**S<k+1> commitment:** #.. (<owner>), ...
**Demo path:** <working | broken at step N | unknown>
**Commit:** <sha of main>
```

Keep it to what someone who missed the meeting needs. The final presentation is built from these comments.
