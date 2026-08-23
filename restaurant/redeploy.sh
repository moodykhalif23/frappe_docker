#!/usr/bin/env bash
# Re-deploy an existing install: pull, rebake, roll, refresh caches.
#
# Nobody is logged out. Sessions live in the database; clear-cache only drops
# redis-held page scripts, styles and boot info, so browsers pick the new
# version up on their next request while staying signed in.
#
#   ./restaurant/redeploy.sh            # SITE read from .env
#   SITE=pos.example.com ./restaurant/redeploy.sh

set -euo pipefail
cd "$(dirname "$0")/.."

SITE="${SITE:-$(sed -n 's/^FRAPPE_SITE_NAME_HEADER=//p' .env | tail -1)}"
IMAGE="custom-erpnext:${ERPNEXT_VERSION:-v16.6.0}"
[ -n "$SITE" ] || { echo "no SITE and none in .env"; exit 1; }

log() { echo "==> $*"; }

log "pulling"
git pull --ff-only

log "rebaking the patch layer (stamps a fresh build id onto asset URLs)"
DOCKER_BUILDKIT=1 docker build -t "$IMAGE" -f patch-restaurant.dockerfile .

log "rolling containers"
docker compose up -d
for _ in $(seq 1 40); do docker compose exec -T backend true 2>/dev/null && break; sleep 2; done

log "migrating ${SITE}"
docker compose exec -T backend bench --site "$SITE" migrate

log "custom fields"
echo 'from restaurant_management.house import ensure_custom_fields; ensure_custom_fields()' \
  | docker compose exec -T backend bench --site "$SITE" console >/dev/null

log "clearing server caches (sessions untouched)"
docker compose exec -T backend bench --site "$SITE" clear-cache
docker compose exec -T backend bench --site "$SITE" clear-website-cache || true

log "done — reload the POS tab, no re-login needed"
