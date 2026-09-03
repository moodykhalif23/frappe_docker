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

# The patch layer builds FROM the base image. After a pin change that base does
# not exist on this box yet, and docker would try to pull it from the hub.
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "No ${IMAGE} on this machine — the pinned versions changed."
  echo "This is a version move, not a redeploy. Run instead:"
  echo "  SITE=${SITE} ./restaurant/upgrade.sh"
  exit 1
fi

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

CF_ZONE_ID="${CF_ZONE_ID:-$(sed -n 's/^CF_ZONE_ID=//p' .env | tail -1)}"
CF_API_TOKEN="${CF_API_TOKEN:-$(sed -n 's/^CF_API_TOKEN=//p' .env | tail -1)}"
if [ -n "$CF_ZONE_ID" ] && [ -n "$CF_API_TOKEN" ]; then
  log "purging the Cloudflare edge cache"
  curl -sS -X POST "https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}/purge_cache" \
    -H "Authorization: Bearer ${CF_API_TOKEN}" -H "Content-Type: application/json" \
    --data '{"purge_everything":true}' | grep -o '"success":[a-z]*' || echo "purge request failed"
else
  log "no CF_ZONE_ID/CF_API_TOKEN in .env — skipping the edge purge"
fi

log "done — reload the POS tab, no re-login needed"
