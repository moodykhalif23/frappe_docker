# Browser test

`flow.mjs` drives the whole pass in a real browser: sign in, load the floor,
sign a waiter on with a PIN, seat a walk-in, open the pad, create and select an
order, ring up a dish, dispatch it, check the tile badge, then re-check the
floor at tablet and phone widths. It screenshots every step into `shots/`.

```bash
npm i          # playwright, pinned in package.json
BASE=https://pos.example.com USER_=Administrator PASS=... \
  WAITER="Amina Otieno" PIN=4821 GUEST="Test Party" node flow.mjs
```

It writes real records. Run it against a demo site, or delete the guest's
booking, order and customer afterwards.

**Why this exists.** Four defects shipped past a full API-level suite and were
only caught here: an appended IIFE parsed as a call and blanked the floor; a
`?v=` cache-buster broke frappe's asset loader; `set_route` with a query string
raised "Page not found"; and a seated table had no customer, so the pad refused
to open an order. `node --check` and green server tests say nothing about
whether the page runs.

## The rest of the suite

| file | what it proves | how |
|---|---|---|
| `flow.mjs` | sign in, floor, waiter PIN, seat, order, dispatch, badge, responsive | browser |
| `door.mjs` | the door panel opens, a party queues, seating lands on the pad | browser |
| `checkout.mjs` | seat → dish → pay, then the table is free and the turn is on the board | browser |
| `turn_test.py` | seat → sit → pay → free, and the Table Turns report | server |
| `staff_test.py` | waiter ↔ Employee, PIN writes attendance, roster reads it | server |
| `stock_test.py` | sale → recipe → issue, idempotent, waste, restock, variance | server |
| `seats.mjs` | two parties share a table, each with its own check and waiter | browser |
| `drill2.mjs` | the handover drill: manager + two waiters by PIN + kitchen + till, in the second room, every fence, close-day lockout | browser |
| `card_shots.mjs` | the menu card: photo, name, price, `- n +` pill driving the check | browser |
| `drill.mjs` | the eight-terminal live drill (four parties, one table, split, concurrent payments) | browser |
| `rename_probe.mjs` | rename a table through the floor editor's Update Table dialog and read the record back | browser |
| `live_smoke.mjs` | post-deploy proof on a live site that leaves the books untouched: PIN, seat, fire, kitchen ticket, till reaches pay, then Release | browser |

Test-site helpers: `mirror_stations.py` recreates the live station accounts,
waiters and a second room on a local site; `reset_floor.py` cancels every open
check and party (refuses on a non-local site); `probe_shared.mjs` watches the
pad while a second party is seated. `run-all.sh` runs the seven suites and
prints one verdict.

```bash
BASE=https://pos.example.com PASS=... node door.mjs

docker cp restaurant/e2e/turn_test.py "$(docker compose ps -q backend)":\
/home/frappe/frappe-bench/apps/restaurant_management/restaurant_management/turn_test.py
echo 'exec(open("/home/frappe/frappe-bench/apps/restaurant_management/restaurant_management/turn_test.py").read(), globals()); run()' \
  | docker compose exec -T backend bench --site pos.example.com console
```

Both server suites clean up after themselves and raise on failure, so a green
run ends with `ok` and a red one ends with a traceback.

`cleanup.py` removes what the browser suites leave behind — parties, bookings,
the test waiter and its employee record. It never cancels a submitted invoice:
it reports them and leaves the decision to a person.

**`checkout.mjs` takes a real payment.** It submits a POS Invoice, which lands
in the books — on a client's site that is a fake sale on their ledger. It
refuses to run against a non-local `BASE` unless `ALLOW_REAL_SALE=1`, and the
invoice it creates has to be cancelled afterwards. The browser tests do not
clean up after themselves; the server suites do.

`staff_test.py` needs hrms; without it every check but the first is skipped.
