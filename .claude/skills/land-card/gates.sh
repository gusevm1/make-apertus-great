#!/usr/bin/env bash
# Every check a branch has to pass before it lands. Run from anywhere inside the worktree.
set -euo pipefail
# The last line names the result, so it survives a pipe that hides the exit code.
gate="worktree-env"
trap 'if [ $? -eq 0 ]; then echo "GATES PASSED"; else echo "GATES FAILED: $gate"; fi' EXIT
root="$(git rev-parse --show-toplevel)"

# Without .env a worktree's docker compose recreates the shared src-db-1.
if [ "$(git rev-parse --path-format=absolute --git-dir)" != "$(git rev-parse --path-format=absolute --git-common-dir)" ] && [ ! -f "$root/.env" ]; then
  echo "This worktree has no .env. Run .claude/skills/build-card/worktree-env.sh <card number> first." >&2
  exit 1
fi
gate="skills"

python3 "$root/.claude/skills/scrum-board/board.py" --demo
python3 "$root/.claude/skills/build-card/wait.py" --demo

# The app brings its own checks (format, types, tests, build) in src/gates.sh.
gate="src"
if [ -x "$root/src/gates.sh" ]; then "$root/src/gates.sh"; fi
