# Floor audit: what is actually true on Etham's live site

Read off `frappe.ikobriq.com` on 8 September 2026 by eight parallel surveys, each
establishing the mechanism from the code in the built image and then the state
from the live database. Written so that nothing in this deployment is an
assumption when an audit or a second restaurant arrives.

**Status of the evidence.** The surveys completed. The adversarial verification
did not: 24 of 55 agents died on an account spend limit, including every
verifier for people, integrity and scaling, and the completeness critic. So the
findings below are single-source unless marked corroborated, and some may be
overstated. Each carries the query or code path that produced it, so any of them
can be checked in minutes. Treat this as a list of things to confirm, not a
verdict.

Nothing in this document was changed on the live site. It is all read-only.

---

## The seven that would hurt in an audit

### 1. Only the shift-opener's sales reach the ledger

erpnext collects a closing entry's invoices with `build_invoice_query` filtered
on `owner == user`, where `user` comes from the **opening** entry. A POS Invoice
is owned by whoever was logged in at the pay screen. So when a second person
takes payment, their sales are never consolidated and never reach the general
ledger.

On live this is not theoretical: **KES 2,610 of one day's takings cannot reach
the ledger**. Corroborated independently by the money and integrity surveys.

### 2. Two paid sales were deleted today, and the number was re-used

`ACC-PSINV-2026-00082` appears **twice** in `Deleted Document`, both cancelled
then deleted by `geff@etham.co.ke`: a KES 130 sale rung by the cashier at
11:22, and a second sale numbered identically. Their `Table Order` rows still
read Invoiced against an invoice that no longer exists. About KES 760 left the
day's record.

### 3. Deleted document numbers come back

frappe's `revert_series_if_last` decrements the counter when the newest document
in a series is deleted, so the next document takes the same name. On live, **10
of 12 deleted invoice numbers and 47 of 54 deleted check numbers have been
re-issued**. Two different bills carried `ACC-PSINV-2026-00082` on the same day.

For VAT and for eTIMS this is a bright-line failure: the invoice number is the
key a tax authority uses to match the customer's copy to the seller's.

### 4. The drawer is never counted

`make_closing_entry_from_opening` writes each reconciliation row with
`opening_amount: 0` and `expected_amount: <sum of payments>`, never touches
`closing_amount`, and `close_day` submits it directly. Every closing entry on
live therefore asserts a **nil cash difference against a count nobody took** —
opening 0, counted 0, difference 0, while expecting real money (one closing
expects Cash 3,490 and M-Pesa 7,510).

The one document whose purpose is to prove the money banked matches the money
rung currently proves nothing, and is self-contradictory on its face.

### 5. Open checks are deleted during service

Since 5 September, **seven open checks worth KES 1,240 were deleted**, six of
them by the cashier account. Ordered food erased rather than voided. This is the
classic route for both theft and unrecorded staff meals, and the only trace is
the `Deleted Document` table.

### 6. Any station login is an administrator of its own tenant

`restaurant_management.api.call` is whitelisted and does
`frappe.get_doc(model, name)`, `getattr(doc, method)`, then calls it with
arbitrary keyword arguments. No method allowlist, no doctype restriction, no
permission check. **Any logged-in station can read every waiter's PIN**, and
therefore seat and fire as anyone.

While this endpoint exists, "a waiter cannot edit their own sales" is false, and
attribution is testimony rather than evidence.

### 7. The PIN is four digits with no rate limit

`house.waiter_sign_in` is callable by any logged-in user and verifies the PIN
with no attempt counter and no lockout, so a tablet can walk all 10,000
combinations. The signed-in token then lasts 12 hours.

---

## Cost of sales does not exist

Etham has traded **KES 33,770 across 94 invoices** with no cost side at all: 0
stocked ingredients, 0 recipes, 0 stock entries, 0 stock ledger entries, 0 bins,
and no GL entry against cost of goods sold. The income side is well documented;
the expense side is entirely outside the system.

Worse, `backflush()` sets `restaurant_backflushed = 1` on every pending invoice
**even when it issues nothing** — so 143 invoices are flagged "stock consumed"
with no consuming document behind them. The audit trail asserts something false,
permanently and silently.

---

## The kitchen question, answered

Not unconfigured, not broken: **configured and never used.**

Both production centres carry a complete routing table (Kitchen 16 item groups,
Bar 5) and the full `Sent → Processing → Completed → Delivered` chain. All 21
routed groups exist. Every one of the 218 unfired lines belongs to a routed
group, so the boards *would* show them.

Nobody has pressed Order since 3 September. Two related faults make that easy to
miss:

- The pay screen carries a green **Order** button that says "This action sent all
  order to Production Center" and then only sets the *check's* status to Sent.
  Every line stays at Attending, so no board query matches and the lines can
  never advance.
- The **guest tracker** reads line status, so a guest sees "Placing order",
  0 of 4, forever, including after paying.

One scaling fault sits here too: payment never closes a line out, and the board's
query filters parents only by company, so it sends **an `IN` clause containing
every check the site has ever had** on each refresh. At Etham's 30 checks a day
that is roughly 11,000 names after a year.

---

## Two on the menu that will cost money

- **Two dishes read identically and differ by KES 50.** `Minji` (300, imported
  24 Aug) and `minji plain` (item_name "minji", 250, created by Geff on 7 Sep)
  are both on the menu, both Veg, both in the same group. The pad shows
  `item_name`, so a waiter sees "minji" twice. Both have sold.
- **An unpriced item rings up at 0.00 and nothing refuses it.** Verified link by
  link: no Item Price gives `price_list_rate: None`, the card renders 0.00, and
  the line saves at zero. Onboarding is exactly when unpriced items exist.

---

## Multi-tenant: five things the plan missed

The plan's model (a site per restaurant) stands. These are gaps in it.

1. **`deploy.sh` re-pins `FRAPPE_SITE_NAME_HEADER`.** The plan's central change
   is to unset that variable, and its onboarding command wraps `deploy.sh` —
   which writes it back unconditionally. So **onboarding tenant N+1 routes the
   entire existing fleet at the new tenant.** A till would ring a sale into
   another company's books. This is the sharpest failure mode in the whole
   exercise: gaining a tenant breaks the ones you have.
2. **A bake migrates one tenant while the new image serves all of them.**
   `redeploy.sh` rolls every service, then migrates `$SITE` only. Nothing
   enumerates sites, so the rest are left half-upgraded until a screen touches a
   missing column.
3. **Per-site provisioning is not part of migrate.** `after_migrate` never calls
   `house.ensure_custom_fields()`, so a correctly created tenant looks installed
   and is not.
4. **Seven of the fourteen gating suites write to whatever site they are given.**
   Only `day_prep.py` is fenced to `*.localhost`. One environment variable stands
   between a rehearsal and fabricated invoices plus a submitted closing entry in
   a real ledger. A canary tenant is by definition a real restaurant.
5. **A bad bake has no rollback image.** `redeploy.sh` re-tags in place, which
   makes the previous bake dangling, and the host cron at 02:20 prunes dangling
   images. Today that is one client; with ten tenants it is ten incidents and
   nothing to roll back to.

---

## What I would do first

In this order, because this is the order in which they cost money or credibility.

1. **Stop the ledger hole** (finding 1). Until it is fixed, only the person who
   opened the day should take payment, and someone should check that each day's
   closing entry total matches the day's invoices.
2. **Remove delete rights on submitted sales** (findings 2, 3, 5). Cancel leaves
   a record; delete does not, and it re-uses the number. This is a permission
   change, not code.
3. **Guard `api.call`** (finding 6). An allowlist of methods and a permission
   check. Everything about attribution rests on it.
4. **Count the drawer** (finding 4). The close dialog should ask for the counted
   cash and record the variance.
5. **Decide about the kitchen.** Either configure the habit and use the boards,
   or accept a ring-and-bill operation and stop carrying the unused flow.
6. **Fix `deploy.sh`** before a second tenant exists (multi-tenant 1).

Findings 1 to 5 are business and configuration decisions more than code. That is
deliberate: most of what an auditor would object to here is not a bug, it is a
control that was never put in place.
