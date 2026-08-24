#!/usr/bin/env bash
# Move an existing install onto a new pin set (see restaurant/PINNED_APPS).
#
# Unlike redeploy.sh this expects the app versions themselves to have changed,
# so it rebuilds the base, runs the framework's own migrations, and re-asserts
# what actually landed. It never drops data and never force-pushes an image:
# the previous tag stays on the box as the rollback.
#
#   SITE=pos.example.com ./restaurant/upgrade.sh
#
# Take a backup first — the script refuses to run without a recent one.

set -euo pipefail
cd "$(dirname "$0")/.."

SITE="${SITE:-$(sed -n 's/^FRAPPE_SITE_NAME_HEADER=//p' .env | tail -1)}"
TAG="${CUSTOM_TAG:-$(sed -n 's/^CUSTOM_TAG=//p' .env | tail -1)}"
IMAGE="custom-erpnext:${TAG}"
FRAPPE_PIN="$(sed -n 's/^frappe=//p' restaurant/PINNED_APPS)"
[ -n "$SITE" ] || { echo "no SITE and none in .env"; exit 1; }
[ -n "$TAG" ] || { echo "no CUSTOM_TAG in .env"; exit 1; }

log() { echo "==> $*"; }

log "checking for a backup of ${SITE} taken today"
if ! docker compose exec -T backend bash -lc \
  "ls sites/${SITE}/private/backups/\$(date +%Y%m%d)*-database.sql.gz >/dev/null 2>&1"; then
  echo "No backup from today. Run this first, then re-run the upgrade:"
  echo "  docker compose exec -T backend bench --site ${SITE} backup --with-files"
  exit 1
fi

log "building ${IMAGE} — frappe ${FRAPPE_PIN} + the pinned apps"
DOCKER_BUILDKIT=1 docker build \
  --secret id=apps_json,src=apps-restaurant.json \
  --build-arg FRAPPE_BRANCH="$FRAPPE_PIN" \
  --build-arg CACHE_BUST="$(sha256sum apps-restaurant.json restaurant/PINNED_APPS | sha256sum | cut -c1-16)" \
  -t "$IMAGE" -f images/layered/Containerfile .

log "applying the restaurant patch layer (asserts the pins before it starts)"
DOCKER_BUILDKIT=1 docker build -t "$IMAGE" -f patch-restaurant.dockerfile .

log "rolling containers onto ${IMAGE}"
docker compose up -d
for _ in $(seq 1 60); do docker compose exec -T backend true 2>/dev/null && break; sleep 2; done

log "migrating ${SITE} (the framework's own patches — this is the slow part)"
docker compose exec -T backend bench --site "$SITE" migrate

log "custom fields the floor hangs on stock doctypes"
docker compose exec -T backend bench --site "$SITE" console <<'PY'
from restaurant_management.house import ensure_custom_fields
print(ensure_custom_fields())
PY

if ! docker compose exec -T backend bench --site "$SITE" list-apps 2>/dev/null | grep -q '^hrms'; then
  log "installing hrms"
  docker compose exec -T backend bench --site "$SITE" install-app hrms
else
  log "hrms already installed"
fi

log "refreshing caches — nobody is logged out, sessions live in the database"
docker compose exec -T backend bench --site "$SITE" clear-cache
# frappe versions asset URLs off this file's mtime; touching it is what gets a
# CDN to serve the new bundle. Never append a query string of your own.
docker compose exec -T backend touch sites/assets/assets.json
docker compose restart frontend

log "what landed:"
docker compose exec -T backend bench --site "$SITE" list-apps

cat <<'NEXT'

==> now prove it, before anyone serves a table:

  docker cp restaurant/e2e/turn_test.py "$(docker compose ps -q backend)":\
/home/frappe/frappe-bench/apps/restaurant_management/restaurant_management/turn_test.py
  echo 'exec(open(".../turn_test.py").read(), globals()); run()' \
    | docker compose exec -T backend bench --site SITE console

  cd restaurant/e2e && BASE=https://SITE PASS=... node flow.mjs && node door.mjs

  checkout.mjs bills a real invoice — demo sites only (ALLOW_REAL_SALE=1).

==> rollback: put the previous tag back in .env as CUSTOM_TAG, `docker compose
    up -d`, and restore the backup with `bench --site SITE restore <file>`.
NEXT
