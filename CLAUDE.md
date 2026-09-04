# frappe_docker fork — Restaurant POS kit

Fork of frappe/frappe_docker carrying a one-click restaurant POS deploy
(ERPNext v16 + alphabit-technology's `restaurant_management`). Everything
specific to this fork lives in `restaurant/` — start with
[restaurant/README.md](restaurant/README.md) for the user-facing story.
This file is the working knowledge for developing and debugging it.
[restaurant/OPERATIONS.md](restaurant/OPERATIONS.md) is the behavioural spec —
how a real restaurant runs, and which of those rules the app still breaks.

## Start here

`docs/HANDOFF.md` — what is live for Etham right now, how to reach the server,
what is shipped and what is deliberately not. Read it before touching anything.

## Layout

- `apps-restaurant.json` — apps baked into the image (erpnext pinned + restaurant app), fed to `images/layered/Containerfile` as the `apps_json` build secret.
- `patch-restaurant.dockerfile` — post-build layer applying all app fixes; `FROM custom-erpnext:<tag>` onto itself and re-tags.
- `restaurant/deploy.sh` — the one-click. Re-runnable; every step skips what exists.
- `restaurant/demo_seed.py` — bootstrap()/seed()/seed_inventory()/simulate()/sell_one()/backflush()/layout_floor(). Environment-agnostic: discovers or creates company, room, POS profile, warehouse; can complete the setup wizard headlessly.
- `restaurant/patches/` — multi-line source patches COPY'd + appended by the patch dockerfile (sed handles only one-liners).

## Iron rules (each learned the hard way)

1. **Verify fixes inside the image**, never by reading the dockerfile or a live container: `docker run --rm custom-erpnext:<tag> grep -c <fix> <file>`. Live-container seds evaporate on the next `compose up`; a sed that doesn't match exits 0 silently.
2. **Every patch step must be idempotent** — the patch dockerfile builds FROM its own output, so steps run again on every rebake. Guard appends with `grep -q` on a *distinctive* token: `grep -q restaurant_manage` once matched `restaurant_management` and silently skipped a patch.
   Mind the strip step too: appended blocks are cut and re-appended every bake, so **anything a
   later patch appends after them is cut as well** — a helper `def` appended to the end of
   `table_order.py` vanished on the first rebake while its guard marker (inside the class) stayed,
   and every check open died with `NameError`. Insert helpers at the module head, and guard each
   edit of a file by its own token.
   And when a patched block *changes*, the guard must recognise the **previous bake's output** and
   upgrade it — the base image already carries the old block, so "already applied → exit" freezes
   the old text forever (the M-Pesa refusal stayed a dialog for two bakes this way).
3. **Site name must equal the public domain** (`SITE=pos.example.com`). The nginx template rewrites the `Origin` header to the site name and frappe's websocket auth requires `Host == Origin` — mismatch = "Invalid origin", dead realtime/kitchen display. For local work use `SITE=pos.localhost` — **and** the websocket service must be able to `fetch("http://<site name>/api/...")` to authenticate each socket (it uses the rewritten Origin as the URL). Public domains resolve via real DNS; `*.localhost` needs `restaurant/compose.localhost.yaml` (deploy.sh adds it to COMPOSE_FILE automatically: frontend gets the site name as a network alias + nginx listens on :80). Never add that override on a public deployment — the alias would shadow real DNS and break the https auth fetch. Symptom of missing override: browser console shows `Error connecting to socket.io: Unauthorized: TypeError: fetch failed`, nothing on the floor live-updates.
4. Rebuilding from `apps-restaurant.json` alone produces an **unpatched** image — always follow with the patch dockerfile build. `deploy.sh` does both.
5. Commits: single-concern, author `moodykhalif23 <brian@sozuri.net>`, never add an AI co-author.
7. **Pin what you build on.** `restaurant/PINNED_APPS` records the exact
   erpnext and hrms tags and the restaurant app's commit; `assert_pins.py` runs
   first in the patch dockerfile and fails the bake on any mismatch. The
   restaurant app tracks a **tagless master**, and bench clones with `--branch`,
   which will not accept a bare SHA — so master is asserted rather than pinned.
   If upstream moves, the build stops with the old and new commits: review the
   diff (our patches anchor on exact source), re-test, then update PINNED_APPS.
   To get a real pin, fork the app, tag the commit and point
   `apps-restaurant.json` at the fork.

8. **Editing `apps-restaurant.json` does not bust the build cache.** It is
   mounted as a BuildKit *secret*, and secrets are excluded from the cache key,
   so `bench init` is reused and the new pin never lands — the build succeeds,
   takes long enough to look real, and the image still holds the old version.
   Pass the layered Containerfile's `CACHE_BUST` arg, which exists for this and
   is interpolated into the `bench init` RUN:
   `--build-arg CACHE_BUST=<pin>-<date>`. `--no-cache-filter builder` does
   *not* do it — it was tried and the builder layer was still reused.
   Confirm in the image afterwards, reading the app rather than the manifest:
   `docker run --rm --entrypoint bash custom-erpnext:<tag> -lc \
   'grep -m1 version apps/hrms/hrms/__init__.py'`. `assert_pins.py` is the
   backstop — it fails the patch bake when the image disagrees with
   `PINNED_APPS`.

9. **Move erpnext and hrms together.** hrms from v16.5.1 writes
   `Accounts Settings.repost_allowed_types` during install; erpnext only grew
   that field later, so an old erpnext under a current hrms dies with
   `AttributeError: repost_allowed_types` at `install-app`. Pinning hrms *down*
   to dodge it strands the stack a year behind — pin both to a current pair
   instead. `restaurant/PINNED_APPS` is the single source of truth and
   `deploy.sh` reads the frappe pin from it; its `CACHE_BUST` is the hash of
   that file plus `apps-restaurant.json`, so a pin change can no longer be
   silently ignored by the build cache.

10. **frappe is pinned to a tag, not `version-16`.** The tag names the app
   clone *and* the `frappe/build` + `frappe/base` image tags, so a rebuild a
   year from now reproduces this image instead of picking up whatever
   `version-16` points at that day.

6. **Flatten the image every few bakes.** The patch dockerfile builds `FROM`
   its own output, so each bake adds ~50 layers. Past roughly 480 the overlayfs
   mount option string exceeds the kernel limit and *every* build fails with
   `mount source: "overlay" ... err: no such file or directory` on an arbitrary
   early step. Running containers keep working and pruning the build cache does
   not help, so it reads as cache corruption — it isn't. Check with
   `docker inspect custom-erpnext:v16.6.0 --format '{{len .RootFS.Layers}}'`
   and run `restaurant/flatten-image.sh` (export/import to one layer, config
   carried across).

## v16 traps in the restaurant app (all patched here; details in restaurant/README.md)

- Doctype typo `Sales Taxes And Charges` + nonexistent column `amount` (→ `tax_amount`) in `table_order.py`.
- `aggregate()` crashes on `NULL` totals — None-guards added.
- Desk **page scripts run in a closure** in v16: the page's `var RM` never reaches `window`, but every class asset file reads `RM` globally → blank floor. Fixed with `window.RM = ...`. Same trap for the page's `const [TRANSFER, UPDATE, DELETE, INVOICED, ADD, QUEUE, SPLIT, ...]` — the class files read them globally, so realtime handlers died with `ReferenceError: ADD is not defined` (symptom: +Table/+Room saves to DB but the floor never updates). Exported to `window` in the patch layer.
- **v16 validates link fields before any doc hook fires** (both insert and save paths, see `frappe/model/document.py`) — `before_insert` is too late to fix up a link. Intercept by overriding the controller's `insert()`/`save()` (see `restaurant/patches/restaurant_booking_append.py`).
- `Restaurant Booking`/`Table Order` grant only `Restaurant Manager`/`Restaurant User` roles — System Manager alone gets Permission Error, which also aborts the floor/order-pad JS init. `seed()` grants the roles to staff users.
- `TableOrder.send` is a **@property** — attribute access fires kitchen dispatch; calling it throws `'dict' object is not callable` (a sync payload also lands on the instance as `.send`).
- POS Settings must be in "POS Invoice" mode (v16 defaults to Sales Invoice mode, blocking the app's billing); UOM `Nos` allows fractions for by-the-glass recipes (production: use a dedicated fractional UOM instead).
- The order pad's catalog comes from **`POS Profile.restaurant_menu`** (app custom field) — unset means an empty menu no matter what the Restaurant Menu contains. The Veg/Non-Veg tabs filter on `Item.item_type`. `seed()` sets both.
- v16 renamed `get_item_details`' kwarg `args`→`ctx` — unpatched, every add-to-cart 500s and the cart silently stays at 0.
- Kitchen/Bar production-center boards are **empty until an order is dispatched** — and dispatching is a **double-click** on the pad's green Order button (single click does nothing by design).

- **Restaurant Permissions are an empty whitelist.** `Restaurant Settings.restaurant_access()`
  filters rooms, tables, order counts and `can_access()` through the `Restaurant Permission`
  table for anyone without System Manager / Restaurant Manager — and nobody ever fills that table
  in, so a station holding only `Restaurant User` saw a floor with **no rooms**, a pad that
  died before its menu loaded, and `Cannot read properties of undefined (reading 'select')`.
  It is why the stations were first given Restaurant Manager (which let them delete tables).
  `floor_visibility.py` makes an empty table mean "unrestricted"; the fences stay on DocPerms.
- **Deleting a waiter poisons the books.** `waiter` is a Link on POS Invoice, and closing
  the day re-saves every invoice during consolidation, so one deleted waiter = the shift can
  never bank — and erpnext rolls the closing entry back then fails to comment on it, so the
  till only ever saw the *masking* `Could not find Reference Name: POS-CLO-…`. The waiter
  controller now refuses the delete (`waiter_not_deletable.py`) and `close_day` restores a
  missing waiter (inactive) before it banks.
- **The Order button trusts a stale server count.** `TableOrder.order()` and the button badge read
  `data.products_not_ordered`, computed by the server when the check was last fetched. On a freshly
  opened pad it is 0 until the next realtime sync, so the button sits disabled and a double-click is
  a silent no-op — every time on the live site (internet latency), never locally (the sync wins the
  race). `order_counts_locally.py` counts the check's own unsent lines. Any "works locally, not
  live" pad symptom: suspect a server-computed field the client reads before the sync lands.
- **A `field:` autoname silently undoes edits to that field.** `Restaurant Object` is named by
  `description` (clean names), and frappe's `_sync_autoname_field()` resets the field to the docname
  on every save of an existing record — so "Update Table" saved the seats and threw the new name
  away with no message. Renaming is an explicit `frappe.rename_doc` (plus the plain-copy `room`
  columns that Link fields do not update); `rename_on_description.py` does it inside `save()`.
- **`desk_form.accept` treats a missing key as blank.** Every field on the Desk Form is written
  onto the document from the posted `data`; a field the client did not send becomes None. Save a
  dialog before its values have loaded and you wipe the record (Update Table set seats to 0).
  `desk_form_partial_save.py` skips unsent fields on update — new records still take every field.
- **A Desk Form blanks its numeric fields on open.** frappe's `FieldGroup.make()` applies field
  defaults after the record loads, and `get_field_default_value` returns an empty default for
  numeric fields (it drops it for text). The app's forms bind controls to the record, so the
  loaded number is overwritten with null before the user sees it — then posted back as null.
  `form_keeps_record_values.py` re-applies the record's values after `make()`.
- **The card list is clusterize'd for a one-column list.** `ProductItem.init_clusterize` renders 40
  rows × 4 blocks = 160 cards and pads the rest with a spacer sized one-card-per-row; under the
  four-column grid that is a screenful of blank and dishes 161+ only appear after scrolling through
  it. Hiding the spacer in CSS would lose those dishes — `all_cards.py` renders every dish fetched,
  and one `LIMIT` (1000) governs both `rows_in_block` and the fetch's `page_length` (upstream: 400).
- **`synchronize_order_data` belongs to the pad.** The order pad handles that realtime channel
  expecting an order payload; publishing anything else on it (a "table freed" note) threw
  `Cannot read properties of undefined (reading 'order')` at payment. Fork events get their own
  channel (`rm_table_freed`) and `seats.js` listens for them.
- **Two payloads build a kitchen ticket.** The board's own fetch (`get_command_data`) and
  the one pushed at dispatch (`TableOrder.send` rows) — a field added to one is missing from
  the other, and upstream's `table_info` returns a one-item *tuple*. Patch both or the
  ticket says `undefined` until the board reloads.

## Kit features (added by this fork, shipped via the patch layer)

- **Guest order tracker**: `/assets/restaurant_management/order-status.html?order=<Table Order name>` — no login; polls `restaurant_management.api.order_status` (allow_guest) every 5s and shows per-item progress (Sent → Preparing → Ready → Served). Exposes item names/qty/status only. Order names are sequential — treat links as semi-private; add a token before offering it publicly.
- **Seats, not tables**: occupancy is counted in seats. A party is one
  `Restaurant Booking` carrying its covers and its waiter; a table's free seats
  are `no_of_seats` less the covers on it. Two parties can share a six-top, each
  with its own `Table Order` (`Table Order.booking` links them) and its own
  server, so *Sales by Waiter* splits a shared table correctly. The tile reads
  `5/6` with a badge per party (`AT·2`, `MT·3`); the old single `d-waiter-badge`
  is the **section** and now shows only on a table nobody is sitting at. Server
  side is `house.table_occupancy/table_seats/parties/add_covers/claim_party/
  release_party`; the floor is `restaurant/patches/seats.js`. Requires
  `Restaurant Settings.multiple_pending_order = 1` — `ensure_custom_fields()`
  sets it, and without it the app refuses a second check on a table.
- **The counter is opened by hand**: with no open shift the pad used to fall
  through to erpnext's `create_opening_voucher()`, so the first waiter to ring a
  dish opened the drawer with an uncounted float. `house.open_day()` + an "Open
  day" button now do it deliberately, per mode of payment; billing refuses until
  then. `close_day()` banks the shift **and sweeps**: every table's waiter is
  cleared and every party still sitting is closed, because sections and parties
  are shift-long. That sweep is why leftover `W` badges used to survive the night.
- **Deliveries**: `Restaurant Settings.delivery_room` names the room whose slots are deliveries
  (`house._ensure_delivery()` creates *Delivery* + 3 slots, a *Delivery Charges* income account and one
  `RM Delivery Charges` record — the admin sets `default_rate`, nothing is hard-coded). `seat_walkin`
  flags a check seated there (`is_delivery`, `delivery_notes` = address · phone, `charge_amount` = fee);
  `delivery_ticket.py` books the fee to the account at `make_invoice`, makes `get_delivery_address`
  fall back to the typed text, and adds `is_delivery/customer/delivery_address` to **both** ticket
  payloads. Riders are `Restaurant Waiter`s; *Sales by Waiter* has a Room filter for their commission.
- **Attribution**: no anonymous transaction. `seat_walkin` requires a verified waiter (PIN or
  token); the pad's Order goes through `house.dispatch(order, waiter, token)`, which stamps
  `Order Entry Item.waiter` on every fired line and adds a timeline comment. The tablet asks the PIN
  again after `Restaurant Settings.waiter_recheck_seconds` (blank = 90; 1 = every time) via
  `RM_waiter.confirm()`. *Sales by Waiter* credits the check owner or the line firer.
  The pad's + and a dish tapped with no check both open Seat guest locked to the table
  (`RM_host_stand.open_for`, `pad_plus_seats.py`) — upstream's `add_order` made anonymous checks.
- **M-Pesa by code**: an M-Pesa payment row must carry the customer's 10-character confirmation
  code, unused before — asked for on the pay form (`mpesa_code.py`), enforced and stored as
  `Sales Invoice Payment.reference_no` in `make_invoice` (`mpesa_reference.py`), printed on the
  receipt, listed by the *M-Pesa Payments* report. Mode detection is the name matching `m-?pesa`.
- **Menu item editor**: Menu Management screen has a "New Item" button and tapping a card's price pill opens an edit dialog (name, category, price, Veg/Non-Veg, photo). Backed by `restaurant_management.api.upsert_menu_item`/`get_menu_item` (appended via `restaurant/patches/api_append.py`); writes land on Item / Item Price / Restaurant Menu, so frappe stays the system of record.

## Working on it

- Run seed functions via console (NOT `bench execute` — the module doesn't resolve there, and piped multi-line IPython mangles indentation):
  `echo 'exec(open("apps/restaurant_management/restaurant_management/demo_seed.py").read(), globals()); seed()' | docker compose exec -T backend bench --site <site> console`
  The script lives in the container only after `deploy.sh` copies it — re-copy after container recreation.
- **A shift opened on an earlier date puts "Yesterday's shift is still open" over every page**, and its
  backdrop swallows every tap — suites fail with "+ does nothing" and no error. `run-all.sh` banks a
  stale local shift first (`e2e/day_prep.py`); never point that at a live site.
- The floor layout is data: each `Restaurant Object` carries `data_style` JSON (x/y/z/width/height). `layout_floor()` re-grids everything; origin starts at x=60 — the desk sidebar no longer overlaps the page (see below).
- Full-POS look: `restaurant-manage` passes `hide_sidebar: true` to `make_app_page` (v16 built-in; the container auto-restores the sidebar on route change). The footer "Close" link navigates back to `/app`; the accounting shift-close (POS Closing Entry) stays in the page menu, Shift+Ctrl+C.
- Paying a check frees **that party's** seats, not the table:
  `free_table(table, booking=...)`. `TableOrder.make_invoice` passes its own
  booking — without it, paying one check evicts the strangers next to them.
- Inventory model: dishes are non-stock; 20 stocked ingredients + a BOM per dish; `backflush()` posts one Material Issue covering all un-flushed POS Invoices (tracked via a `RESTAURANT-BACKFLUSH:` tag in Stock Entry remarks). Run at day end or via cron.
- DB access: `docker compose exec -T backend bench --site <site> mariadb < file.sql`. MariaDB root password defaults to `123` (compose default) unless `DB_PASSWORD` is set.

## Redeploying

`restaurant/redeploy.sh` — pull, rebake, roll, migrate, clear caches. Nobody is
logged out: sessions live in the database, and `clear-cache` only drops
redis-held page scripts, styles and boot info.

Browser caching bites hard, and the origin lies to you. Frappe appends
`?v=<version>` to each asset it fetches, where the version is
`os.path.getmtime(sites/assets/assets.json)`. Patching JS in place never
touches that file, so the URL is unchanged — and Cloudflare fronts this site
caching `/assets` for `max-age=14400`, keyed on the full URL. The edge
therefore serves the **pre-patch** body for four hours while `curl` against
127.0.0.1:8080 shows the patch present. Diagnose with
`cf-cache-status` and always fix it by bumping the version:

    docker compose exec -T backend touch sites/assets/assets.json

frappe re-imports a standard workspace only when the JSON's `modified` is **newer than the
stored row**, so a patch that adds a shortcut must stamp the JSON with the bake time — a fixed
date left *M-Pesa Payments* (and four other shortcuts) missing on live until a forced import.

`redeploy.sh` does this. The `app_include_js`/`app_include_css` helpers are a
second trap: frappe emits them as **bare** `/assets` URLs, so the edge served the
pre-deploy `drag.js` and form classes for hours after every deploy —
`versioned_includes.py` stamps them with the bake id in `hooks.py`, and
`redeploy.sh` purges Cloudflare when `CF_ZONE_ID`/`CF_API_TOKEN` are in `.env`.
Open tabs are the third: frappe reloads a tab only for its own version bump, so a floor
opened before a redeploy runs the old patch layer until reloaded — `RM_seats.watch_build()`
polls `house.asset_version()` and reloads at a quiet moment.
**Never append your own query string to a `frappe.require` asset
path** instead: `assets.extn()` reads the extension from *after* the `?`, so
`x.js?v=1` resolves to no handler and the whole floor fails to load. Each bake
stamps `window.RM_BUILD` purely so you can tell which build a browser has.

`node --check` is not enough for these appends. It validates syntax, and the
failure mode here is runtime: the page file ends in a class expression with no
terminator, so an appended `(` reads as a call. Blocks are separated with `;`,
and the only real check is loading the page in a browser.

## Live deployment

One production instance runs at frappe.ikobriq.com (site named exactly that) on a VPS shared with other services; Caddy fronts it → 127.0.0.1:8080. Its server-side clone of this repo tracks `origin/main`. Credentials are not in this repo — ask the owner.
