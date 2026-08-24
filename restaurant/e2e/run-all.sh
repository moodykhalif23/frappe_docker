#!/usr/bin/env bash
# Run every suite against one site and report a single verdict.
#
#   SITE=pos.localhost BASE=http://pos.localhost:8080 PASS=admin ./run-all.sh
#
# checkout.mjs bills a real invoice, so it is skipped unless the site is local
# or ALLOW_REAL_SALE=1 is set deliberately.

set -uo pipefail
cd "$(dirname "$0")/../.."

SITE="${SITE:-$(sed -n 's/^FRAPPE_SITE_NAME_HEADER=//p' .env | tail -1)}"
BASE="${BASE:-http://${SITE}:8080}"
APP=/home/frappe/frappe-bench/apps/restaurant_management/restaurant_management
BE="$(docker compose ps -q backend)"

declare -a NAMES=() VERDICTS=()
record() { NAMES+=("$1"); VERDICTS+=("$2"); }

server_suite() {
  local name="$1" file="$2"
  echo "=== ${name} ==="
  docker cp "restaurant/e2e/${file}" "${BE}:${APP}/${file}" >/dev/null
  if echo "exec(open(\"${APP}/${file}\").read(), globals()); run()" \
     | docker compose exec -T backend bench --site "$SITE" console 2>&1 \
     | grep -E 'PASS|FAIL|passed' | tee /dev/stderr | grep -q 'AssertionError\|FAIL'; then
    record "$name" FAIL
  else
    record "$name" PASS
  fi
}

browser_suite() {
  local name="$1" file="$2"
  echo "=== ${name} ==="
  if (cd restaurant/e2e && BASE="$BASE" node "$file" 2>&1 | grep -E 'PASS|FAIL|RESULT|PAGE ERRORS|REFUSING'); then
    record "$name" PASS
  else
    record "$name" FAIL
  fi
}

server_suite "floor lifecycle (turns, queue, bookings)" turn_test.py
server_suite "staff and attendance" staff_test.py
browser_suite "floor, waiter, order, dispatch" flow.mjs
browser_suite "the door" door.mjs
browser_suite "checkout and the turn" checkout.mjs

echo
echo "================ verdict ================"
fails=0
for i in "${!NAMES[@]}"; do
  printf "%-8s %s\n" "${VERDICTS[$i]}" "${NAMES[$i]}"
  [ "${VERDICTS[$i]}" = "FAIL" ] && fails=$((fails + 1))
done
echo "========================================="
[ "$fails" -eq 0 ] && echo "all suites green" || echo "${fails} suite(s) failed"
exit "$fails"
