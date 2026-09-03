# Where this repo is (2026-09-02)

## Handover state, 2 September 2026

Accounts on the live site: `admin@etham.co.ke` (everything), `geff@etham.co.ke`
(the manager — menu, recipes, stock, suppliers, staff, reports, the day),
`cashier@`, `waiter@`, `kitchen@` (stations). Rooms: **Main Hall** (Table 1, 2,
4, 5, 6) and **R 2** (Table 7–10, four seats each). One waiter on the PIN list:
`sharon` (PIN verified server-side).

The handover drill (`restaurant/e2e/drill2.mjs`: manager + two waiters by PIN +
kitchen screen + till, working R 2) found and fixed, in this order:

1. **Stations saw an empty floor.** Anyone without Restaurant Manager was filtered
   through the empty `Restaurant Permission` table — no rooms, a pad that never
   loaded its menu. Broken on live since Restaurant Manager was taken off the
   stations (54c1852). `floor_visibility.py`.
2. **A second waiter's taps did nothing** on a shared table: the pad opened with
   no check selected and a swallowed "whose check?" dialog blocked input for 15 s.
   The pad now opens on the check the waiter just seated. `pad_pick_on_open.py`,
   `host_stand.js`, `seats.js`.
3. **The kitchen ticket read `undefined`** and never named the waiter: the
   dispatch payload is built separately from the board's fetch.
   `kitchen_ticket_waiter.py`.
4. **The day could not be banked** once a waiter had been deleted (dead Link on
   every invoice; erpnext masks the real error). Waiters with history can no
   longer be deleted, and `close_day` restores a missing one before banking.
5. **A manager could not price a new dish** (Item Price wanted Sales Master
   Manager) and **nobody could add a Supplier or a BOM** — roles granted on live,
   `menu_price_perm.py` for the price.
6. A kitchen screen that landed on R 2 (tables only) showed nothing — it now
   opens where the boards are. `seats.js` + `house.board_room`.

7. **The order pad's cards** were rebuilt to the client's reference: photo on
   top, name, price left, a `− n +` pill right where n is what is on the check.
   `+` is the app's own add-item control; `−` takes one off the way the cart's
   trash does. `card_layout.py` + `menu_card.css`; `card_shots.mjs` proves it.

8. **Order was a silent no-op on a fresh pad — on live only.** The button and its
   badge trust `products_not_ordered`, a server count that is 0 until the next
   realtime sync; on the internet the tap beats the sync, locally it never did.
   Found by `live_smoke.mjs` after the deploy. `order_counts_locally.py`.

9. **Renaming a table from "Update Table" was silently reverted** (seats saved,
   name did not). Since clean_names made the description the docname, frappe's
   `_sync_autoname_field()` put the old name back on every save. A changed
   description now renames the record and relabels every open floor.
   `rename_on_description.py`, `rename_refresh.py`. Reported by Etham on 3 Sep.

The books were purged for handover on the afternoon of 2 Sep: the two screenshot-test
invoices, two stale checks and the three 14:52 test checks on Table 7 are gone —
0 POS Invoices, 0 open checks, 0 open parties. Etham can start trading clean.

---

# Where this repo was (2026-08-26)

Written for whoever opens a session **inside `/home/patch/frappe_docker`**. The
Sokisoko platform is a different repo and a different conversation; nothing here
depends on it beyond sharing one server.

## The client

**Etham Eatery** — a real restaurant, live on **https://frappe.ikobriq.com**.
They are trading. Treat every change as production.

## What is running

| | |
|---|---|
| image | `custom-erpnext:v16.32.3` (tag follows the erpnext pin) |
| pins | frappe v16.31.0, erpnext v16.32.3, hrms v16.16.0, restaurant_management master `c55ac4ae` |
| site | `frappe.ikobriq.com`, company **Etham Eatery** (abbr `ETH`), currency KES |
| data | 170 menu items, 13 tables, 5 rooms, 1 POS profile (`Etham`) |
| rollback | `.env.before-v16.32.3` on the box. No older image remains on the server (the v16.6.0 one is gone; dangling layers were pruned 2 Sep) — roll back by checking out the previous commit and rebaking, ~5 min |

Server access: SSH as **`sokisoko@194.163.136.175`** (key auth works). That user
**cannot read `/home/frappe/frappe_docker`** — it is `0750 frappe:frappe` — but it
*is* in the `docker` group, so reach the repo through a helper container:

```bash
docker run --rm -v /home/frappe/frappe_docker:/repo alpine:3 ls /repo
```

`root@` and `frappe@` reject the key; those were always typed by hand.

## Shipped and tested

- **Floor**: door panel (waitlist, reservations, empty-table list), waiter PINs,
  table-turn metrics, delete-a-table that says what blocks it.
- **Staff**: waiter → Employee link; the PIN pad writes Employee Checkins (hrms).
- **Stock**: sales spend stock through each dish's BOM (idempotent), waste with a
  mandatory reason, **Restock List** and **Consumption Variance** reports.
- **Open/close day**: the counter no longer opens itself when the first order is
  rung — a manager opens it with a counted float per mode of payment. Closing
  shows what it will bank, refuses over open checks, and sweeps the floor: table
  sections cleared, parties still sitting closed.
- **Seats, not tables**: a six-top with two guests has four seats to sell. Two
  parties can share a table, each with its own check and its own waiter; the
  tile reads `5/6` with a badge per party. *Sales by Waiter* splits a shared
  table correctly because the waiter is on the party, not the table.

Suites: `restaurant/e2e/run-all.sh` — floor 33, staff 13, stock 25, plus four
browser suites (`flow`, `door`, `seats`, `checkout`). All seven green locally on
`custom-erpnext:v16.32.3`; **not yet deployed to frappe.ikobriq.com**.

Deploying the seat model needs `ensure_custom_fields()` (it adds
`Restaurant Booking.waiter`, `Table Order.booking`, `POS Invoice.booking` and
sets `Restaurant Settings.multiple_pending_order`) — `redeploy.sh` runs it. The
box's image was at 427 layers and had to be flattened before it would build;
check `docker inspect ... {{len .RootFS.Layers}}` there too.

## The gap that matters

Stock **machinery** is live but Etham's **data** is not: 0 BOMs, 0 stock entries.
Until their real ingredients, recipes and opening counts are loaded, every stock
number would be invented — which is exactly what the client asked us to remove.
The intake path is `docs/Etham-Stock-Flow-and-Manual.pdf`.

## Next: KRA eTIMS

See `docs/ETIMS-SCOPE.md`. Short version: it is blocked on a commercial
registration, not on code, and it hooks **POS Invoice** — the till.

## House rules that cost us time to learn

Read `CLAUDE.md` first — the iron rules are all scar tissue. The three that bite
hardest:

1. Verify a fix **inside the image**, never from the dockerfile or a live
   container. Live-container edits vanish on the next `compose up`.
2. A pin change does not bust the build cache (`apps-restaurant.json` is a
   BuildKit secret). Use the `CACHE_BUST` arg.
3. Bust the asset cache **after** restarting the frontend — its entrypoint
   re-links assets and resets the mtime, silently undoing an earlier touch.

Deploy with `restaurant/upgrade.sh` for a version move, `redeploy.sh` for a
same-version rebake, or `make help`. Build the image **locally and ship it** —
the box has ~7.9 GB RAM shared with another production stack and a frappe asset
build can take it down.
