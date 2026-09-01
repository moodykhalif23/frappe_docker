---
title: "Etham Eatery POS — Admin & Manager Guide"
subtitle: "Everything you self-serve, straight to the point"
date: "August 2026"
---

# How to use this guide

Every task is numbered steps. Every screen is written as **where you type it**.
The one skill that replaces most phone calls: press **Ctrl + K** (or tap the
search bar) anywhere in the back office and type the name of the thing —
`Item-wise Sales Register`, `Restaurant Waiter`, `BOM` — and press Enter.
Everything in this guide can be reached that way.

Two places you will live in:

| Place | Address | What it is |
|---|---|---|
| **The floor** | `frappe.ikobriq.com/app/restaurant-manage` | Tables, orders, kitchen, payments — daily service |
| **The back office** | `frappe.ikobriq.com/app` | Items, recipes, staff, reports, settings |

---

# 1. The system in one line

**Menu items** (with optional **recipes**) are sold on the **floor** (seat →
order → kitchen → pay → receipt), and everything lands in **reports** — sales
by dish, by waiter, by table, and stock used.

---

# 2. The daily rhythm

1. **Cashier opens the day** — floor → **Open day** → count the actual float
   into each box → *Open the day*. Nothing can be billed before this.
2. Service runs: waiters seat and order, kitchen cooks off its screen, cashier
   takes payments.
3. **Cashier closes the day** — floor → **Close day**. It shows what it will
   bank and refuses if checks are still open. Closing also clears every
   waiter's tables and any party still marked seated.

> A day left open overnight blocks tomorrow's sales. If billing is ever
> "refused", check this first: was the day opened today?

---

# 3. Reports — including your best sellers

Press **Ctrl + K**, type the report name, press Enter. Bookmark the ones you
use — the star icon next to the report title.

| The question you're asking | Type this into search |
|---|---|
| **Which food sells the most?** | `Item-wise Sales Register` |
| Sales trend by week / month / item group | `Sales Analytics` |
| Who sold what — per waiter, covers, average check | `Sales by Waiter` |
| How tables turned, longest sitters | `Table Turns` |
| Today's receipts, one by one | `POS Invoice` |
| What is on the shelf right now | `Stock Balance` |
| Every stock movement, in and out | `Stock Ledger` |
| What to reorder | `Restock List` |
| What was used vs what recipes say (waste/theft) | `Consumption Variance` |

**To see your most consumed food:** open **Item-wise Sales Register**, set the
date range at the top, then click the **Qty** column header to sort — your best
sellers are now at the top. Click **Amount** instead to rank by money. Use the
menu (⋮) → *Export* for Excel.

> The three stock reports stay empty until your ingredient lists and recipes
> are loaded (section 5). Sales reports work from day one.

---

# 4. The menu — add, edit, remove a dish

**Add or edit (the easy way, on the floor):**

1. Floor → tap the **pencil** (top-left of the room bar) → **Menu**.
2. **New Item** button → name, category, price, Veg/Non-Veg, photo → Save.
3. To change a price: tap the **price pill** on any card, edit, Save.
4. **Remove** on a card takes it off the menu (the item's sales history stays).

**Rules that save you a phone call:**

- A dish only appears on the order pad if it is on the **Restaurant Menu**
  attached to the POS Profile — the New Item button does this for you; items
  created any other way must be added to the menu too.
- Veg/Non-Veg controls which tab the dish shows under on the pad.
- Only **admin** can edit the menu. The cashier and waiter accounts cannot —
  by design.

---

# 5. Recipes (BOMs) — how a bale of wheat becomes counted dishes

This is what turns on the three stock reports. Order matters:

**a) Create each ingredient once** — search `Item` → *Add Item*:

1. Name it (e.g. *Wheat Flour*), Item Group *Raw Material*.
2. Tick **Maintain Stock**. Unit = what the kitchen measures in (*Kg*).
3. If you buy it in a different unit (a *bale*), add a row under **Units of
   Measure**: Bale = 25 Kg. You'll receive bales; the system counts kg.

**b) Enter what's on the shelf today** — search `Stock Entry` → *Add* →
type **Material Receipt** → warehouse *Stores - ETH* → one row per ingredient
with today's counted quantity and what it cost → Save → Submit.

**c) Give each dish its recipe** — search `BOM` → *Add BOM*:

1. **Item** = the dish (e.g. *Chapati*). Quantity = 1.
2. Under items, one row per ingredient with the amount **one plate** uses
   (0.12 Kg flour, 0.01 L oil…).
3. Save → **Submit**. Repeat per dish — start with your top 20 sellers, add
   the rest as you go.

**d) That's it.** Each night the system reads everything sold, walks the
recipes, and deducts the ingredients in one stock entry. From then on: *Stock
Balance* = what you have, *Restock List* = what to buy, *Consumption
Variance* = the gap between what recipes say you used and what counting says —
that gap is your waste or leakage.

**Restocking later:** every delivery = one *Stock Entry → Material Receipt*
(bales in, kg counted). Waste = *Stock Entry → Material Issue* with a reason.

---

# 6. Waiters — add, rename, deactivate

Search `Restaurant Waiter`:

1. **Add** → real name (the floor badge is built from it — *Sharon* shows as
   **SH**), a 4-digit **PIN**, and a badge colour per person.
2. **Leaving staff: untick Active.** Never delete a waiter — their past sales
   keep their name.
3. Optional: link an **Employee** record and the PIN also clocks them in/out
   for attendance.

On the floor, waiters tap **Waiter → name → PIN** once per shift. Seating a
guest demands this — every party is owned by whoever seated it, and *Sales by
Waiter* is built from that.

---

# 7. Tables and rooms

All of it on the floor, behind the **pencil** (tap once to edit, again to
finish):

| Task | How |
|---|---|
| Add a room/floor | pencil → **+** at the right end of the room bar |
| Delete a room | select it → pencil → **Delete** → confirm (must be empty of tables) |
| Add a table | pencil → **+ Table** |
| Delete a table | pencil → **×** on the tile → confirm |
| Rename / set seats | pencil → **Edit** on the tile → Description / No of Seats |
| Move / resize | pencil → drag the tile or its corners |

**Seats matter**: the seat count is what "Seat guest" uses to offer tables,
and it is how two parties can share one table — the tile reads `5/6` with a
badge per party, each with its own check and its own waiter.

---

# 8. Who can do what — the station accounts

| Login | For | Can | Cannot |
|---|---|---|---|
| `waiter@etham.co.ke` | waiter tablets | seat, order, send to kitchen | take money, open/close day, void tables, edit menu |
| `kitchen@etham.co.ke` | kitchen/bar screens | see and advance tickets | everything above |
| `cashier@etham.co.ke` | the till | payments, open/close day, release tables | edit the menu |
| `admin@etham.co.ke` | you | everything | — |

**Two layers, and only devices log in.** Each tablet or screen signs into the
site **once** with its station account and stays signed in: waiter tablets as
`waiter@`, the kitchen screen as `kitchen@`, the till as `cashier@`. The
**people** never log in — a waiter identifies on the shared tablet with their
name + PIN (floor → *Waiter*), once per shift. That PIN is what puts their name
on parties, orders and the sales report. Kitchen and cashier need no PIN — the
station login is their identity.

When setting a PIN on the Restaurant Waiter form, the field shows dots — tap
the **eye icon** to see what you typed before saving; a hidden typo is the
usual cause of "Wrong PIN". (The little "Weak" meter next to the PIN is
cosmetic — a 4-digit PIN is expected.)

These are enforced by the server, not by hiding buttons — a waiter who taps
*Complete* is refused, with the action logged under their session. **Change
all passwords on first use**: avatar (bottom-left) → *My Settings* → *Reset
Password*.

To add another user: search `User` → *Add* → email + name → under *Roles*
copy the roles from the station account that matches the job.

---

# 9. Billing a shared table — four guests, four waiters, one table

The table tile shows every party: `7/10` with a badge per party (`AM·2`,
`MO·3`…). Each party has **its own check, owned by the waiter who seated
them** — four different waiters on one table is normal, and *Sales by Waiter*
credits each correctly.

**The cashier settles them one at a time:**

1. Tap the table. The pad **asks "Whose check is this?"** — every party is
   listed with the guest's name, covers and waiter. Pick one.
2. **Complete** → take the payment (cash, M-Pesa, or several lines mixed) →
   the receipt prints.
3. Paying frees **only that party's seats** — the tile drops from `7/10` to
   `5/10` and the other parties keep eating undisturbed.
4. Tap the table again for the next party. The check chips in the pad's left
   rail (00001, 00002…) switch between parties at any time.

A table with a single party skips the question — its check is selected the
moment the pad opens.

---

# 10. Money rules worth knowing

- **Split bills**: on the check → **Divide** → tick the items moving to the
  new check → each check pays separately, each gets its own numbered receipt.
  For an even split of one bill: **Complete** → add several payment rows
  (Cash + M-Pesa + …) on the one receipt.
- **Release** (floor toolbar) voids a table's unpaid checks and frees its
  seats — cashier/manager only, and it never touches a paid sale.
- Receipts print from the pad after payment and open the print dialog
  automatically. First time on a new tablet: allow pop-ups for the site.

---

# 11. Suppliers and reordering — the full loop

The system ships **ready to buy**: supplier shelves are pre-built (Produce,
Butchery & Meat, Dairy, Dry Goods, Beverages, Gas & Fuel, Packaging, Services)
and stock **asks to be re-bought by itself** the moment an ingredient dips
below its reorder level.

**a) Add each supplier once** — search `Supplier` → *Add*:

1. Name, then pick the **Supplier Group** from the pre-built list.
2. Phone/M-Pesa details under contact — that's all a purchase needs.

**b) Tell each ingredient who supplies it and when to re-buy** — open the
ingredient's Item:

1. Under **Supplier Items**: add the supplier (their item code optional).
2. Under **Reorder**: warehouse *Stores - ETH*, **Reorder Level** (e.g. 10 kg),
   **Reorder Qty** (e.g. 50 kg — two bales), type *Purchase*.

**c) From there the loop runs itself:**

1. Sales consume stock through the recipes (section 5).
2. The moment flour dips below 10 kg, the system raises a **Material Request**
   overnight — no one types anything.
3. Morning routine: search `Material Request` → open the day's requests →
   **Create → Purchase Order** — supplier and quantities are pre-filled from
   (b). One order per supplier, a few taps.
4. Goods arrive: open the PO → **Create → Purchase Receipt** → confirm counts →
   Submit. **Stock goes up, valuation updates** — the bale is now 25 counted kg.
5. The supplier's bill: PO → **Create → Purchase Invoice** → Submit when paid.
   Supplier statements live at `Accounts Payable`.

**Restock List** (section 3) stays the manager's daily glance: everything
under its level, how short, and who supplies it — the same list the automatic
requests are built from.

---

# 12. When something looks wrong

| Symptom | Cause and fix |
|---|---|
| "Billing refused" / counter closed message | The day isn't open, or yesterday's is still open. **Open day** / **Close day** as cashier. |
| Cashier taps Complete, gets "Not order Selected" | No check picked on a shared table — tap the table again and answer "Whose check?", or tap the check chip in the left rail. |
| A dish is missing from the pad | It's not on the Restaurant Menu — add it via Menu → New Item, or check its Veg/Non-Veg tab. |
| A table shows occupied but nobody's there | An unpaid check is holding it — **Release** (cashier). |
| Stock reports are empty | Recipes/opening counts not loaded yet — section 5. |
| A waiter "can't do" something | That's the fence (section 8). Use the right station login. |
| Anything else | Search `Error Log` as admin — the newest entry usually names the problem. |

**Backups** run automatically every night at 02:30 and are kept 14 days on the
server. Restoring is a support task — call before touching anything if data
looks wrong.
