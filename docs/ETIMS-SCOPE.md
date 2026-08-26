# KRA eTIMS for Etham — what it would actually take

Raised because `overrides/apps.txt` on the server turned out to be shell history
pasted into a file by mistake, containing a URL for `kenya-compliance-via-slade`.
Nothing references it; the app was never installed. If Etham needs eTIMS, this is
the shape of the work.

## First, a question only the client can answer

**Is Etham registered for VAT, and are they already filing through eTIMS by some
other means (a POS supplied by a vendor, a bureau, a spreadsheet)?**

That answer changes everything below. eTIMS obligations in Kenya now reach past
VAT-registered businesses — expense deductibility depends on it — but the exact
duty for this business is a question for their accountant, not for us to assume.
Do not scope the build before it is answered.

## Two apps exist, and only one is viable

| | `kenya-compliance-via-slade` | `kenya-compliance` |
|---|---|---|
| route to KRA | via **Slade 360 Advantage** (Savannah Informatics) | direct to eTIMS **OSCU** |
| v16 support | `version-16` branch, tag `16.5.2` | not stated |
| maintained | active branches | **"no longer in active development"** |
| registration | handled by the vendor | you apply to KRA as self- or 3rd-party integrator, described by its own README as "the difficult part" |

**Take the Slade one.** An unmaintained app is not a foundation for a legal
obligation, and the direct route puts the KRA approval burden on us. The direct
app also issues its communication key **once** — lose it and you are back to KRA.

## The real blocker is commercial, not technical

Before a line of code matters:

1. Etham (or we, on their behalf) registers for KRA/VSCU — the vendor runs this,
   contact `etims@savannahinformatics.com`.
2. A Slade 360 Advantage account and credentials.
3. Company PIN, branch ID and device details recorded against the ERPNext company.

Treat this as **lead time in weeks**, not a sprint. Nothing can be tested end to
end until sandbox credentials exist.

## What it touches — and why that is the risk

The app hooks **Item, Customer, Sales Invoice, POS Invoice, Stock Ledger Entry**
and purchase documents. `POS Invoice` is our till: it is the document the floor
submits on every payment, and the one our back-flush reads.

The danger is plain: **if eTIMS submission is synchronous and KRA is slow or
down, the restaurant cannot take money.** Any integration must submit in the
background and never block `POS Invoice.submit()`. Prove that with the network
blackholed before it goes anywhere near a Friday service.

## The work, once unblocked

1. Add the app to `apps-restaurant.json` **pinned to a tag**, record it in
   `restaurant/PINNED_APPS`, rebuild the base with `CACHE_BUST` (iron rule 8).
2. Check our patch layer for collisions — we already patch `table_order.py`,
   `pay-form-class.js` and POS Invoice custom fields.
3. Configure against **sandbox** credentials first.
4. Extend `restaurant/e2e/` with an eTIMS suite: an invoice submits, a failure
   queues and retries, and a KRA outage does not stop a sale.
5. Item classification is data entry: every one of the 170 menu items needs a KRA
   classification code and UOM mapping. That is the client's work, like recipes.
6. Deploy behind the usual gate — build locally, ship the image, `upgrade.sh`.

## Honest estimate

Integration and tests: a few days once credentials exist. Registration and the
item classification pass: unknown, driven by KRA and by Etham. The classification
of 170 items is likely the longest pole after registration.
