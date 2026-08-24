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
IMAGE="custom-erpnext:${CUSTOM_TAG:-$(sed -n "s/^CUSTOM_TAG=//p" .env)}"
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

# Cloudflare caches /assets for 4h keyed on the full URL including frappe's
# ?v=<mtime of sites/assets/assets.json>. Patching JS in place never changes
# that mtime, so browsers keep the pre-patch file. Bump it.
log "bumping the asset version so browsers refetch"
docker compose exec -T backend touch sites/assets/assets.json

log "clearing server caches (sessions untouched)"
docker compose exec -T backend bench --site "$SITE" clear-cache
docker compose exec -T backend bench --site "$SITE" clear-website-cache || true

log "done — reload the POS tab, no re-login needed"
