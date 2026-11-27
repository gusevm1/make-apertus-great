---
name: refine-issue
description: Turns a rough idea or a Backlog card into one an agent can build without asking questions, or says why it can't be. Use this when someone gives you a feature idea to put on the board, asks to "refine", "groom", "write up" or "split" a card, asks whether a card is ready, and for every Backlog card before a sprint boundary.
---

# Refining a card

An agent that picks up a card can't ask anyone what was meant. So a card is ready only when someone who has never heard of it could build it and a reviewer could check it. Your job is to get it there, or to say exactly what is missing. You propose; the PO decides. Never move a card to Ready.

## 1. Read

`python3 .claude/skills/scrum-board/board.py show <n>` (or take the idea you were given), then `docs/demo-path.md` and the part of the code it touches. Read the code: most bad cards are wrong about what already exists.

## 2. Judge

- **Ready:** the acceptance criteria are checkable, it fits one sprint (about 3 hours for one agent, review included), and nothing in it needs a human decision.
- **Needs rework:** the intent is clear but the criteria are vague, missing or not checkable. Rewrite it.
- **Too large:** it won't fit one sprint. Split it into cards that each work end to end and say which comes first (`after #<n>`).
- **Needs the PO:** it depends on a choice only a human can make (scope, wording, which data, what the demo shows). Ask; don't guess.

A card that serves no step of the demo path is fine, but say so. The PO should know what they are spending a sprint on.

## 3. Post one comment

Don't edit the card's body. Comment on it (`gh issue comment <n> --body ...`), so the author sees what changed and can disagree:

```
**Refinement: <ready | needs rework | too large | needs the PO>**

**Proposed card**
## Why
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

**Size:** <S | M>

**Split** (only if too large)
1. <title>: <one line>
2. <title>: <one line>, after 1

**Questions for the PO** (only if any)
1. <question a human can answer in one line>
```

For a new idea with no card yet, create it with the proposed card, from `## Why` to `## Demo-path step`, as the body, then post any questions as a comment on it:

```
board add --title "<what>" --size <S | M> --priority P2 --body "<proposed card>"
```

Use P2 unless the PO named a priority. After that, Priority is the PO's to change, not yours.

For an existing card, set the size if it is missing: `board set <n> --size S`. Leave Priority and Sprint alone.

## Rules

- Report what you don't know instead of filling it in. An invented requirement is worse than an open question.
- Don't design the solution. `## What` names what gets built and where, and the criteria say what must be true afterwards. Neither says how to code it.
- Write the card as `scrum-board` describes under "Writing a card": concrete names and numbers, under about 25 lines, with the `unslop` skill applied.
- Create the split cards only once the PO agrees to the split.
