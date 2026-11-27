#!/usr/bin/env bash
# Gives this worktree its own banking API, ports and .env, so several agents can build at once.
# Usage, from anywhere inside a worktree: .claude/skills/build-card/worktree-env.sh <card number>
# RESET=1 in front starts the banking API again with fresh demo data.
set -euo pipefail
card="${1:?Usage: worktree-env.sh <card number>}"
root="$(git rev-parse --show-toplevel)"
main="$(git worktree list --porcelain | head -1 | cut -d' ' -f2-)"
api_port=$((8100 + card % 800))
app_port=$((3100 + card % 800))
container="trustroom-api-c${card}"

if [ "$root" = "$main" ]; then
  echo "This is the main checkout. It keeps its own .env and ports; run this in a worktree." >&2
  exit 1
fi
if [ ! -f "$main/.env" ]; then
  echo "No .env in $main. It needs LLM_NAME, LLM_BASE_URL and LLM_API_KEY." >&2
  exit 1
fi

# Widgets, uploads and /admin/reset live in the banking API, so each card gets its own.
# ponytail: OCR (4 GB) and the MCP server hold no state and stay shared on 8002 and 8001.
if [ "${RESET:-}" = "1" ]; then docker rm -f "$container" >/dev/null 2>&1 || true; fi
docker start "$container" >/dev/null 2>&1 || docker run -d --name "$container" -p "$api_port:8000" \
  -e DEMO_TODAY=2026-11-27 ghcr.io/tiziano-schacht-ti8m/trustroom-banking-api:latest >/dev/null

{
  grep -vE '^(BANKING_API_URL|APP_PORT)=' "$main/.env"
  echo "BANKING_API_URL=http://localhost:$api_port/api"
  echo "APP_PORT=$app_port"
} >"$root/.env"

# gates.sh runs the frontend checks, and a fresh worktree has no node_modules.
if [ ! -d "$root/src/frontend/node_modules" ]; then
  echo "Installing the frontend's packages (npm ci in src/frontend)"
  (cd "$root/src/frontend" && npm ci --no-audit --no-fund --loglevel=error)
fi

echo "banking API: http://localhost:$api_port   your app: port $app_port"
echo "When the card is done: docker rm -f $container"
