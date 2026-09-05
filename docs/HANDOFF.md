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

10. **Dragging or resizing an unselected tile did nothing** (upstream): the drag
    bailed out, the mouse-up selected the tile, and a click on a selected tile
    deselects it — so the editor felt like it worked once and then stopped.
    A drag now selects the tile as it starts. `drag_selects.py`. Reported 3 Sep.

11. **Update Table could wipe the seat count** (upstream): `desk_form.accept`
    writes every field of the form and takes a missing key as blank, so saving
    before the values had loaded set seats to 0 — it happened to Etham's first
    save on 3 Sep (4 → empty) and to my probe (9 → empty; put back to 9). An
    existing record now keeps any field the form did not send.
    `desk_form_partial_save.py`.

12. **The dialog opened with the seat count blank** — the real cause behind 11.
    frappe's FieldGroup applies each field's default *after* the record loads,
    and an empty default is applied to numeric fields (ignored for text), so
    No of Seats and Minimum Seating were blanked on open and posted as null.
    The record's values are now put back over the defaults.
    `form_keeps_record_values.py`.

13. **Deliveries** (feature, 3 Sep): a *Delivery* room with three slots, an
    income account and one `RM Delivery Charges` record the admin edits (fee 0
    until set). A check seated on a Delivery slot is flagged, carries the typed
    address and phone to both kitchen-ticket payloads, opens the pay screen as
    a delivery with the fee filled in, and books the fee to its own account
    line. Riders are waiters with PINs; *Sales by Waiter* gained a **Room**
    filter for their commission base. Upstream's fee path keyed on an Address
    field and a doctype that do not exist here — replaced. Delivery slots sort
    last in the seat dialog, so a walk-in never defaults to one ("Delivery 1"
    sorts before every "Table"). `delivery_ticket.py`, `house._ensure_delivery`,
    `host_stand.js`.

14. **160 of 170 dishes on the pad, and a screenful of blank under them.** The
    card list is virtualised in blocks of 40 rows × 4; a four-column grid
    rendered 160 cards and hid the rest behind a spacer sized for one card per
    row. Every dish fetched now renders at once, and one limit (1,000) governs
    both the fetch and the render — upstream's own fetch stopped at 400 per
    view; categories and search refetch server-side beyond that. `all_cards.py`;
    `menu_blank_probe.mjs` and `card_shots.mjs` assert it. Reported 3 Sep.

15. **A resize or move could be lost, and the tile snapped back even when saved.**
    `save_config()` returned silently whenever any other save was in flight
    (`window.saving`) — on the internet those windows are long — so the gesture
    never reached the server and a hard refresh showed the old size. And
    `set_style` broadcast the tile it had loaded *before* writing, so every
    floor snapped the tile back. Now a save waits its turn, and the broadcast
    carries what was written. `tile_save_reliable.py`.
16. **Old JavaScript served after a deploy, "new browser" or not.** The helper
    scripts in `app_include_js` (drag.js, the form classes…) were emitted as
    bare URLs; Cloudflare holds `/assets` for 4 h keyed on the URL, so a device
    could get the pre-deploy `drag.js` — intermittent floor-editor behaviour.
    Each bake now stamps those includes (`versioned_includes.py`), and
    `redeploy.sh` purges the edge when `CF_ZONE_ID`/`CF_API_TOKEN` are in `.env`.

17. **A tab opened before a redeploy kept running the old scripts** — frappe only
    reloads a tab when *its own* version changes, so the fixes above were live
    on the server while the editor's tab still dropped saves and snapped tiles
    back ("shows for a few seconds, then returns"). The floor now compares the
    version it loaded with the server's every two minutes and reloads itself
    at a quiet moment (no dialog, no drag). `house.asset_version`, `seats.js`.

18. **Freeing a table told nobody.** `free_table` cleared the tile with
    `set_value`, which publishes nothing, so a paid delivery slot (or any
    table) stayed "seated" on every floor until the 60-second poll or a
    reload. It now pushes the freed tile and nudges the seat badges.
19. **Receipts opened a second tab and waited for a click.** The receipt and the
    table bill now print from a hidden frame in the same tab: the dialog
    appears the moment payment confirms; Chrome's `--kiosk-printing` on the
    till makes it silent. Station Setup 3b.
20. **Card look, second pass** (Etham): 6 px corners, photo flush with the top
    edge, footer wraps instead of overflowing the card on a narrow till; the
    same rules on the pad and on Menu Management.

21. **Attribution — the moat.** A tablet's PIN session was a localStorage entry
    that never expired, so every seat and every fire was credited to whoever
    signed in last. Now: Seat guest and Order each confirm the PIN (admin-set
    grace window, default 90 s, `Restaurant Settings.waiter_recheck_seconds`, 1 = every time);
    seating refuses without a verified waiter; `house.dispatch` fires lines as
    the confirmed waiter, stamps `Order Entry Item.waiter` on each, and leaves a
    timeline note; *Sales by Waiter* gains **Credit = Check owner | Lines fired**.
    `waiter_pad.js confirm()`, `host_stand.js`, `dispatch_identity.py`.

22. **M-Pesa paid with no trace.** A mobile-money payment was an amount and a mode; the
    customer's confirmation code was read aloud and lost, so nothing reconciled against the
    M-Pesa statement. The pay form asks for the code under the M-Pesa amount (`mpesa_code.py`),
    `make_invoice` refuses a row without a well-formed one or with a code that already paid
    another invoice, and stores it as the payment row's `reference_no` (`mpesa_reference.py`);
    the receipt prints it; the *M-Pesa Payments* report lists the day by code.

23. **Initials on the title, a square plus, a visible scrollbar.** The photo placeholder's
    initials are centred with `top:50%`, but `.icon` was never positioned, so the percentage
    resolved against the card — fine on a short card, on the title once a two-line name made the
    row taller. `.icon` is now `position: relative`; the plus is a circle again (the 6px pass had
    squared it); the card list scrolls without a bar. Third pass in `menu_card.css`. Positioning
    `.icon` woke upstream's dormant `top:3px; left:-3px` and shifted the photo off the card edge
    by 3px on live — zeroed; the card suite now checks the photo's offset, not only its width.
    The client's final pick for the quantity control (fifth pass): the pill sits on the card's
    bottom edge, square-cornered, the − and + filling its two ends; the card suite asserts the fit.

24. **A ghost on Table 16.** The tile showed a white dot and looked taken, with no check, no
    party and nobody's badge. The dot is upstream's "a customer is attached" marker, and the pad's
    customer box can attach a name (here `test`) without seating anyone or naming a waiter. The
    floor now heals such leftovers on every occupancy fetch (`house.heal_stale_markers`) and the
    dot is hidden — seats and party badges already say who is where.

25. **Two more doors round the seating rule.** The pad's + called the table's `add_order`
    and opened a check with no party, no covers and no PIN; a dish tapped with no check selected
    did the same. Both now open Seat guest locked to that table — PIN first, seats left shown,
    the new party's check selected in the pad (`pad_plus_seats.py`, `host_stand.open_for`).

26. **"Day closed" hid what stayed open.** Closing the day banks paid sales and sweeps parties;
    it never voids an unpaid check (money), so one stood on Table 14 after the close and the
    message said only "0 table sections released". `close_day` now returns
    `open_checks_detail` and the dialog names each check left standing — table, guest, amount —
    with "settle it or release the table". The check on Table 14 was an anonymous one from the
    old + (finding 25), released by hand.

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
