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
- **Close day**: a button that shows what it will bank and refuses over open
  checks. A shift left open bills into yesterday and then rejects today's sales.

Suites: `restaurant/e2e/run-all.sh` — floor 27, staff 13, stock 25, plus three
browser suites. All green on the deployed image.

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
