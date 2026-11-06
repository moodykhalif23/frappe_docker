#!/usr/bin/env bash
# Redeploy without touching service: bake now, roll after the day is closed.

set -euo pipefail
cd "$(dirname "$0")/.."

SITE="${SITE:-$(sed -n 's/^FRAPPE_SITE_NAME_HEADER=//p' .env | tail -1)}"
IMAGE="custom-erpnext:${CUSTOM_TAG:-$(sed -n "s/^CUSTOM_TAG=//p" .env)}"
[ -n "$SITE" ] || { echo "no SITE and none in .env"; exit 1; }
STAMP="$(date +%Y%m%d-%H%M)"
STAGE="${IMAGE}-next"
BACK="${IMAGE}-pre-${STAMP}"
UNTIL="${UNTIL:-07:00}"
# the helper container runs on UTC; times here are the restaurant's
export TZ="${TZ:-EAT-3}"
log() { echo "==> $(date '+%d %b %H:%M:%S') $*"; }
# python inside the backend, on the live site (the floor's own interpreter)
PY() { docker compose exec -T -w /home/frappe/frappe-bench/sites -e SITE="$SITE" backend \
         /home/frappe/frappe-bench/env/bin/python - "$@" 2>&1 | grep -v RuntimeWarning; }

if [ "${NO_PULL:-0}" != 1 ]; then
  log "pulling"
  before="$(git rev-parse HEAD)"
  git pull --ff-only
  # run as root in a helper, a pull leaves new files root-owned; give them back
  owner="$(stat -c %u:%g .)"
  git diff --name-only "$before" HEAD | while read -r f; do [ -e "$f" ] && chown "$owner" "$f"; done || true
fi
log "repo at $(git log -1 --format='%h %s')"

docker image inspect "$IMAGE" >/dev/null 2>&1 || { echo "no ${IMAGE}: a version move, use upgrade.sh"; exit 1; }
layers="$(docker inspect "$IMAGE" --format '{{len .RootFS.Layers}}')"
if [ "$layers" -gt 200 ]; then
  log "${IMAGE} has ${layers} layers: flattening before the bake (same content, one layer)"
  bash restaurant/flatten-image.sh "$IMAGE" | tail -2
fi

log "baking ${STAGE} (the running containers are not touched)"
DOCKER_BUILDKIT=1 docker build -t "$STAGE" -f patch-restaurant.dockerfile . > "/tmp/bake-${STAMP}.log" 2>&1 \
  || { tail -30 "/tmp/bake-${STAMP}.log"; log "BAKE FAILED: nothing rolled"; exit 1; }
grep -o "patch verification OK[^\"]*" "/tmp/bake-${STAMP}.log" | tail -1 || true

if [ "${NOW:-0}" != 1 ]; then
  log "waiting for the close (no open shift, last closing posted 3+ minutes ago); giving up at ${UNTIL}"
  # busybox date knows hh:mm but not "tomorrow"
  deadline="$(date -d "$UNTIL" +%s)"; [ "$deadline" -gt "$(date +%s)" ] || deadline=$((deadline + 86400))
  state=WAIT; last=""
  while :; do
    state="$(PY <<'PYEOF' | grep -E '^(READY|WAIT)' | tail -1
import os, frappe
frappe.init(site=os.environ["SITE"], sites_path="."); frappe.connect()
open_ = frappe.db.count("POS Opening Entry", {"status": "Open", "docstatus": 1})
c = frappe.db.get_value("POS Closing Entry", {"docstatus": 1}, ["name", "status", "creation"],
                        order_by="creation desc", as_dict=1)
age = int(frappe.utils.time_diff_in_seconds(frappe.utils.now_datetime(), c.creation)) if c else 10**6
ok = not open_ and (not c or c.status == "Submitted") and age > 180
print(("READY" if ok else "WAIT"), "open=%s closing=%s %s age=%ds" % (open_, c and c.name, c and c.status, age))
frappe.destroy()
PYEOF
)" || state="WAIT (state check failed)"
    [ "$state" != "$last" ] && echo "    $(date +%H:%M) $state"; last="$state"
    case "$state" in READY*) break ;; esac
    if [ "$(date +%s)" -ge "$deadline" ]; then
      log "GAVE UP at ${UNTIL}: the day was not closed. Nothing rolled; ${STAGE} is baked and waiting."
      log "to roll it later: NOW=1 NO_PULL=1 ./restaurant/redeploy-after-close.sh"
      exit 2
    fi
    sleep 60
  done
fi

log "ROLLBACK if needed: docker tag ${BACK} ${IMAGE} && docker compose up -d"
docker tag "$IMAGE" "$BACK"
docker tag "$STAGE" "$IMAGE"
log "rolling containers"
docker compose up -d 2>&1 | tail -3
for _ in $(seq 1 60); do docker compose exec -T backend true 2>/dev/null && break; sleep 2; done

log "migrating ${SITE}"
docker compose exec -T backend bench --site "$SITE" migrate 2>&1 | { grep -v '^\s*Updating' || true; } | tail -3
log "custom fields (also puts the bill template onto the bill format)"
echo 'from restaurant_management.house import ensure_custom_fields; print("ENSURE", ensure_custom_fields())' \
  | docker compose exec -T backend bench --site "$SITE" console 2>&1 | grep -E 'ENSURE|Error|Traceback' || true
for _ in $(seq 1 30); do
  curl -sf -o /dev/null -H "Host: ${SITE}" http://127.0.0.1:8080/api/method/ping && break; sleep 2
done
# after the frontend is up: its entrypoint re-links assets and resets this mtime
log "bumping the asset version and clearing caches (sessions untouched)"
docker compose exec -T backend touch sites/assets/assets.json
docker compose exec -T backend bench --site "$SITE" clear-cache
docker compose exec -T backend bench --site "$SITE" clear-website-cache || true
CF_ZONE_ID="${CF_ZONE_ID:-$(sed -n 's/^CF_ZONE_ID=//p' .env | tail -1)}"
CF_API_TOKEN="${CF_API_TOKEN:-$(sed -n 's/^CF_API_TOKEN=//p' .env | tail -1)}"
if [ -n "$CF_ZONE_ID" ] && [ -n "$CF_API_TOKEN" ]; then
  log "purging the Cloudflare edge cache"
  curl -sS -X POST "https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}/purge_cache" \
    -H "Authorization: Bearer ${CF_API_TOKEN}" -H "Content-Type: application/json" \
    --data '{"purge_everything":true}' | grep -o '"success":[a-z]*' || echo "purge request failed"
fi

log "checking what is RUNNING"
want="$(docker image inspect "$IMAGE" --format '{{.Id}}')"
bad=0
for c in backend frontend queue-short queue-long scheduler websocket; do
  got="$(docker inspect "$(docker compose ps -q "$c")" --format '{{.Image}}' 2>/dev/null || echo none)"
  [ "$got" = "$want" ] && echo "    $c on the new image" || { echo "    $c NOT on the new image ($got)"; bad=1; }
done
BE="$(docker compose ps -q backend)"
docker cp restaurant/PATCH_MANIFEST "$BE:/tmp/PATCH_MANIFEST"
docker cp restaurant/patches/assert_markers.py "$BE:/tmp/assert_markers.py"
docker compose exec -T -w /home/frappe/frappe-bench backend python3 /tmp/assert_markers.py || bad=1
PY <<'PYEOF' || bad=1
import os, frappe
frappe.init(site=os.environ["SITE"], sites_path="."); frappe.connect()
a = frappe.db.get_value("Print Format", "Order Account", "html") or ""
b = frappe.db.get_value("Print Format", "Etham Order Bill", "html")
print("    bill format in step with the template:", b is None or a == b)
frappe.destroy()
PYEOF
code="$(curl -s -o /dev/null -w '%{http_code}' -H "Host: ${SITE}" http://127.0.0.1:8080/api/method/ping || true)"
echo "    site ping: ${code}"; [ "$code" = 200 ] || bad=1

log "flattening for the next bake (the running containers keep their image)"
bash restaurant/flatten-image.sh "$IMAGE" | tail -1 || true
docker rmi "$STAGE" >/dev/null 2>&1 || true

if [ "$bad" = 0 ]; then log "DEPLOYED AND VERIFIED"; else log "DEPLOYED WITH FAILED CHECKS: see above; rollback line printed earlier"; exit 3; fi
