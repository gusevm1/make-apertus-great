---
name: land-card
description: Lands a reviewed branch on main without a merge commit, after checking what other agents landed in the meantime. Use this whenever you are about to merge a PR into main, when a push to main was rejected, and when someone asks to "land", "merge" or "ship" a card.
---

# Landing a card

Several agents land on `main` at the same time. A branch that was green an hour ago can be wrong now, because the code under it changed. So landing is a loop: look at what landed, adapt, check again, then push. The push itself is the lock: git refuses it when the branch moved, and you go round again.

## 1. See what landed

```
git fetch origin
git log --oneline HEAD..origin/main
```

No output means nothing landed since you branched. Go to step 4.

## 2. Decide whether it affects you

```
git diff --stat HEAD...origin/main
```

Read the diffs of every file you touch or build on. Read these whenever they changed, whatever your card is:

- prompts and tool descriptions
- shared clients (the model, the banking API) and generated files
- `CLAUDE.md`

Then answer in one line each, for yourself: did a contract I build on change, does someone now do what my card does, does my change break theirs? If yes, change your code. A rebase that applies cleanly proves nothing about meaning.

## 3. Rebase

```
git rebase origin/main
```

- **Conflict:** keep both intents. Never drop another agent's change to make yours fit. If you cannot keep both, comment on their card and block yours.
- **A generated file conflicts:** take theirs, then generate it again and commit the result. Never merge it by hand.
- **Docs tables conflict:** keep both rows.

## 4. Check again

Run `.claude/skills/land-card/gates.sh` on the rebased branch, without a pipe: `| tail` returns the exit code of `tail` and hides a failure. Push only after its last line reads `GATES PASSED`; `GATES FAILED: <gate>` names what broke. If you changed prompts, tools or UI, repeat the matching check from `build-card` step 5. Red means you do not land.

## 5. Push

First check that the card is still yours: `board claim <n> --agent <name>` (`board` is `python3 .claude/skills/scrum-board/board.py`) prints "is yours". If it refuses, another agent took the card over while you were silent: do not push to `main`, comment on the card where your branch stands, and report.

```
git push --force-with-lease origin HEAD
git push origin HEAD:main
```

The first push updates your own PR branch. The second one fast-forwards `main` to exactly the commits you just checked. GitHub then marks the PR as merged.

If the second push is rejected, the branch moved while you were checking. Go back to step 1. That is normal with several agents. The same holds when `wait.py checks` exits 1 saying the PR conflicts: GitHub starts no checks on it until you rebase. After five rounds, say so on the card: someone should let you go first.

## 6. Confirm and tell the others

1. CI (the Board workflow, the only check on a PR into `main`, listed as `sync` in `gh pr checks`) moves the card to Done and closes it. Wait for that first with `.claude/skills/build-card/wait.py status <n> Done`, never with `sleep`, and the Bash `timeout` at 300000 ms. It gives up after 3 minutes with exit 2, or exits 1 with the error when `gh` fails.
2. Only now read the PR state: `gh pr view <pr> --json state -q .state` prints `MERGED`. In the first seconds after the push it still prints `OPEN`; that is expected and is why you wait first. Anything other than `MERGED` after the wait (still `OPEN`, `CLOSED`, or `gh` failing): run `git fetch origin` and `git merge-base --is-ancestor HEAD origin/main`. Exit 0 means your commits are on `main` and GitHub is late, so note it in your report and go on. Exit 1 means the push did not land: go back to step 1 (See what landed), and leave the card as it is.
3. Only when the landing is confirmed and `wait.py` did not exit 0, move the card yourself and note it in your report: `board move <n> done` and `gh issue close <n>`.
4. Comment on the card, so that someone who opens it later sees what was built. Keep it under ten lines and apply the `unslop` skill:

   ```
   ## Implemented
   <one line: what works now>
   - <a behaviour someone can see, with its name or number>
   - <the next one, five at most>

   Where: <the feature folder, endpoint, tool or part of the page>
   Checked: <the command or the steps, and the result as a number>
   Left out: <what the card names and this does not do, or none>
   Changed for others: <every contract or shared file other agents build on, or none>
   ```

5. Delete your branch, but only when item 2 above printed `MERGED`. Deleting the head branch of a PR that GitHub still shows as open closes it unmerged, and CI then moves the card back to Ready. In that case leave the branch and name it in your report.

   ```
   branch=$(git branch --show-current)
   git push origin --delete "$branch"
   git fetch --prune origin
   git switch --detach
   git branch -d "$branch"
   ```

   GitHub deletes the branch of a merged PR by itself, so the push usually fails with `remote ref does not exist`. Go on with the next line either way: the fetch drops the stale `origin/<branch>` from the shared clone. The worktree folder stays.

6. Stop your servers by port.

## Never

- `git push --force` to `main`, and no merge commits there.
- Land with a red gate, or with a gate you skipped.
- Land someone else's branch.
- Resolve a conflict by deleting the other side.
