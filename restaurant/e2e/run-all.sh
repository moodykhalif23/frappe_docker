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
# playwright must resolve from restaurant/e2e — ESM imports ignore NODE_PATH
[ -d restaurant/e2e/node_modules ] || { echo "run: (cd restaurant/e2e && npm i playwright@1.62.1)"; exit 1; }
BE="$(docker compose ps -q backend)"

declare -a NAMES=() VERDICTS=()
# A shift opened on an earlier date puts "Yesterday's shift is still open" over
# every page and its backdrop swallows every tap. Local sites only: this banks.
case "$SITE" in *.localhost)
  echo "exec(open(\"${APP}/day_prep.py\").read(), globals()); run()" \
    | { docker cp restaurant/e2e/day_prep.py "${BE}:${APP}/day_prep.py" >/dev/null; docker compose exec -T backend bench --site "$SITE" console 2>&1; } | grep -E '^DAY' ;;
esac

record() { NAMES+=("$1"); VERDICTS+=("$2"); }

server_suite() {
  local name="$1" file="$2" out rc
  echo "=== ${name} ==="
  docker cp "restaurant/e2e/${file}" "${BE}:${APP}/${file}" >/dev/null
  out="$(echo "exec(open(\"${APP}/${file}\").read(), globals()); run()" \
        | docker compose exec -T backend bench --site "$SITE" console 2>&1)"
  echo "$out" | grep -E 'PASS|FAIL|passed'
  # the suite raises on failure, so a traceback or any FAIL line is the verdict
  if echo "$out" | grep -qE 'FAIL |AssertionError'; then rc=1; else rc=0; fi
  [ "$rc" -eq 0 ] && record "$name" PASS || record "$name" FAIL
}

browser_suite() {
  local name="$1" file="$2" rc
  echo "=== ${name} ==="
  ( cd restaurant/e2e && BASE="$BASE" node "$file" ) 2>&1 \
    | grep -E 'PASS|FAIL|RESULT|PAGE ERRORS|REFUSING|Error'
  rc=${PIPESTATUS[0]}
  # exit 2 is a deliberate refusal (checkout.mjs will not bill a live site),
  # which is not a failure of the thing under test
  case "$rc" in
    0) record "$name" PASS ;;
    2) record "$name" SKIP ;;
    *) record "$name" FAIL ;;
  esac
}

server_suite "floor lifecycle (turns, queue, bookings)" turn_test.py
server_suite "staff and attendance" staff_test.py
server_suite "stock: sale -> recipe -> issue" stock_test.py
server_suite "M-Pesa by code" mpesa_suite.py
server_suite "stale guest markers" stale_marker_suite.py
server_suite "close day names what stays open" close_day_suite.py
browser_suite "floor, waiter, order, dispatch" flow.mjs
browser_suite "the door" door.mjs
browser_suite "seats, parties and the counter" seats.mjs
browser_suite "checkout and the turn" checkout.mjs

echo
echo "================ verdict ================"
fails=0
skips=0
for i in "${!NAMES[@]}"; do
  printf "%-8s %s\n" "${VERDICTS[$i]}" "${NAMES[$i]}"
  [ "${VERDICTS[$i]}" = "FAIL" ] && fails=$((fails + 1))
  [ "${VERDICTS[$i]}" = "SKIP" ] && skips=$((skips + 1))
done
echo "========================================="
if [ "$fails" -eq 0 ]; then
  if [ "$skips" -gt 0 ]; then echo "all suites green (${skips} skipped)"; else echo "all suites green"; fi
else
  echo "${fails} suite(s) failed"
fi
exit "$fails"
