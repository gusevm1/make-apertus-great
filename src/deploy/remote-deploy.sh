#!/usr/bin/env bash
# Runs on the EC2 box in /opt/trustroom, where the Deploy workflow copies it.
# Blue/green without downtime: start the new image as the idle colour, wait until it answers,
# point Caddy at it, then stop the old colour. If the new colour never answers, Caddy keeps the old one.
#
# Usage:    remote-deploy.sh <image>
# Rollback: remote-deploy.sh ghcr.io/gusevm1/trustroom-backend:sha-<previous>
set -euo pipefail

IMAGE="${1:?usage: remote-deploy.sh <image>}"
cd /opt/trustroom
touch active-upstream.caddy

env_get() { grep -m1 "^$1=" .env | cut -d= -f2- || true; }
env_set() {
  if grep -q "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else echo "$1=$2" >>.env; fi
}

docker image inspect "$IMAGE" >/dev/null 2>&1 || docker pull -q "$IMAGE"

# Starts what is missing and leaves running containers alone.
docker compose up -d db searxng banking-api ocr

OLD=$(env_get ACTIVE_COLOR)
if [ "$OLD" = blue ]; then NEW=green; else NEW=blue; fi

echo "--- Starting api-$NEW on $IMAGE (api-${OLD:-none} keeps serving)"
env_set "API_IMAGE_${NEW^^}" "$IMAGE"
docker compose up -d --no-deps --force-recreate "api-$NEW"

HEALTH='import urllib.request; urllib.request.urlopen("http://localhost:8000/api/health", timeout=3)'
for i in $(seq 1 60); do
  if docker compose exec -T "api-$NEW" uv run python -c "$HEALTH" 2>/dev/null; then
    echo "--- api-$NEW answers after about $((i * 2)) s"
    break
  fi
  if [ "$i" = 60 ]; then
    echo "--- api-$NEW never answered. Traffic stays on api-${OLD:-none}." >&2
    docker compose logs --tail 50 "api-$NEW" >&2
    docker compose stop -t 5 "api-$NEW"
    exit 1
  fi
  sleep 2
done

# Written in place: Caddy mounts this one file, and a new inode would stay invisible to it.
printf 'reverse_proxy api-%s:8000\n' "$NEW" >active-upstream.caddy
docker compose up -d --no-deps caddy
docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile
env_set ACTIVE_COLOR "$NEW"

curl -sf -m 5 --retry 10 --retry-all-errors --retry-delay 1 http://localhost:8010/api/health >/dev/null
echo "--- Live: api-$NEW behind Caddy on :8010"

if [ -n "$OLD" ]; then
  # Answers that are still streaming get a minute to finish.
  docker compose stop -t 60 "api-$OLD"
fi

# Keeps the images of both colours, because a stopped container still uses its image.
docker image prune -af >/dev/null
echo "--- Disk: $(df -h / | awk 'NR==2{print $4" free"}')"
