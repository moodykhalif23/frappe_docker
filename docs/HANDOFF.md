# Where this repo is (2026-08-26)

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
| rollback | `.env.before-v16.32.3` on the box + image `custom-erpnext:v16.6.0` |

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
