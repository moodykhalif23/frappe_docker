#!/usr/bin/env bash
# Take a backup and prune old ones. Meant for cron:
#
#   30 2 * * * cd /home/frappe/frappe_docker && ./restaurant/backup.sh >> /var/log/pos-backup.log 2>&1
#
# KEEP_DAYS controls retention (default 14). A backup that lives only on the
# machine it protects is not a backup — set OFFSITE to a path on other storage
# (a mount, an rclone remote target directory) and the newest set is copied there.

set -euo pipefail
cd "$(dirname "$0")/.."

SITE="${SITE:-$(sed -n 's/^FRAPPE_SITE_NAME_HEADER=//p' .env | tail -1)}"
KEEP_DAYS="${KEEP_DAYS:-14}"
OFFSITE="${OFFSITE:-}"
[ -n "$SITE" ] || { echo "no SITE and none in .env"; exit 1; }

log() { echo "[$(date -u +%FT%TZ)] $*"; }

log "backing up ${SITE}"
docker compose exec -T backend bench --site "$SITE" backup --with-files

DIR="sites/${SITE}/private/backups"
newest="$(docker compose exec -T backend bash -lc "ls -t ${DIR}/*-database.sql.gz 2>/dev/null | head -1" | tr -d '\r')"
[ -n "$newest" ] || { log "FAILED: no database dump was written"; exit 1; }

size="$(docker compose exec -T backend bash -lc "stat -c %s '${newest}'" | tr -d '\r')"
# A dump under 10 KB is an empty or broken database, not a small restaurant.
if [ "${size:-0}" -lt 10240 ]; then
  log "FAILED: ${newest} is only ${size} bytes"
  exit 1
fi
log "ok: $(basename "$newest") (${size} bytes)"

if [ -n "$OFFSITE" ]; then
  log "copying the newest set to ${OFFSITE}"
  cid="$(docker compose ps -q backend)"
  mkdir -p "$OFFSITE"
  stamp="$(basename "$newest" | cut -d- -f1)"
  for f in $(docker compose exec -T backend bash -lc "ls ${DIR}/${stamp}* 2>/dev/null" | tr -d '\r'); do
    docker cp "${cid}:/home/frappe/frappe-bench/${f}" "$OFFSITE/" >/dev/null
  done
  log "offsite copy done"
else
  log "NOTE: OFFSITE is unset — these backups only exist on this machine"
fi

log "pruning backups older than ${KEEP_DAYS} days"
docker compose exec -T backend bash -lc \
  "find ${DIR} -type f -mtime +${KEEP_DAYS} -delete 2>/dev/null; ls -1 ${DIR} | wc -l" \
  | tr -d '\r' | xargs -I{} echo "[$(date -u +%FT%TZ)] {} file(s) kept"
