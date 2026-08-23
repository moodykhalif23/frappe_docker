# How the POS must behave — the restaurant operating model

Reference: [eatapp, Restaurant Front of House Management](https://restaurant.eatapp.co/blog/restaurant-front-of-house-management),
cross-checked against [Toast table management](https://support.toasttab.com/en/article/New-POS-Managing-Tables)
and [Lightspeed table service](https://k-series-support.lightspeedhq.com/hc/en-us/articles/360051089273-Adding-orders-in-Table-Service-mode).
This file is the spec: when the app disagrees with it, the app is wrong.

## The sequence of service

1. **Greet** — guest arrives. Walk-in is the normal case, not the exception.
2. **Seat** — host records covers, picks a table that fits, seats the party.
   Tables rotate across servers so nobody gets buried.
3. **Order** — the owning server takes the order; it goes to the kitchen as a
   ticket. Items belong to seats and courses; the server *fires* courses to
   pace the meal.
4. **Cook & run** — BOH prepares; the expo/window is the FOH↔BOH handoff; a
   runner delivers.
5. **Check back** — server monitors the table through the meal.
6. **Pay** — check drops, splits if asked, payment taken.
7. **Turn** — table cleared, reset, marked free for the next party.

## Roles the software has to represent

- **FOH**: host (seats, waitlist), server (owns tables, takes orders, bills),
  bartender, busser (turns tables), runner (delivers).
- **BOH**: kitchen/bar production centres that receive tickets and move them
  Sent → Preparing → Ready → Served.

The app models BOH as **Production Centers** (Kitchen, Bar) with a status
chain, and that side is broadly right. FOH is where the gaps are.

## Rules this implies (and where the app stands)

| Rule | Status |
|---|---|
| A walk-in is seated by **name only** — no customer database search | ✓ host stand: name in, Customer created behind it |
| Seating records **covers** and picks a table that **fits** | ✓ `free_tables(covers)`, tightest fit first, occupied and seated tables excluded |
| Seating leads **straight into the order** | ✓ Seat & open order routes to the table's pad |
| **One server owns a table**, visible on the floor tile | ✗ no waiter field; `Restaurant Object.current_user` is a mutex, not attribution |
| Every check is attributable: **sales by server** | ✗ nothing lands on Table Order or the invoice |
| The floor **never blocks** on shift bookkeeping | ✓ fixed — see below |
| Usable on the device in the server's hand | ✗ desktop-only layout |

## Decisions taken (ikobriq, 2026-08-23)

- **Waiter identity: PIN on a shared terminal.** Waiters do not log in as
  frappe users; they tap a name and a 4-digit PIN to claim a table or send an
  order. No `hrms` on this site, so waiters need their own light record.
- **Cash shift: one house shift.** A manager opens one POS Opening Entry per
  day per POS Profile and every waiter's orders bill into it.

## Build order

1. ✅ **Unblock the floor.** `api.house_shift()` returns the profile's open
   shift whatever user opened it; `restaurant_manage.js` uses it instead of
   erpnext's session-user check, which stranded every other waiter behind a
   "POS Opening Entry Exists" dialog that could never submit.
2. ✅ **Host stand.** "Seat guest" on the floor toolbar: guest name, covers,
   and a table list filtered to what is free and fits (tightest first, tables
   with no capacity recorded offered last and labelled). Seating creates the
   Customer and the booking, then routes to that table's order pad. A seated
   table is excluded immediately — the floor only counts a table busy once
   items are on the order, which would otherwise let the host double-seat it.
3. **Waiter attribution.** Waiter record + PIN, stamped on Table Order and
   copied to the POS Invoice, initials on the floor tile, Sales-by-Waiter
   report (covers, checks, average spend, turn time).
4. **Responsive at every breakpoint** — phone (handheld), tablet (the real
   POS surface), desktop (manager).
