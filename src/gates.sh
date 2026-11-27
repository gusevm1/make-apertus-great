#!/usr/bin/env bash
# The app's own checks. .claude/skills/land-card/gates.sh calls this and prints the result.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"

# Tests run against a real Postgres. --no-recreate keeps a running src-db-1; a db service change needs --force-recreate.
(cd "$here" && docker compose up -d --wait --no-recreate db >/dev/null)

cd "$here/backend"
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest -q
if [ "$(uv run alembic heads | wc -l | tr -d ' ')" != "1" ]; then
  echo "More than one migration head. Point your migration's down_revision at the newest one." >&2
  exit 1
fi

cd "$here/frontend"
npm run format:check
npm run typecheck
npm run test
npm run build
