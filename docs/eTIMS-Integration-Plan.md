# eTIMS: how we will tackle it

Kenya's electronic tax invoicing (eTIMS) is the one compliance gap left in this
kit. It is not scheduled yet, so this document exists to be argued with before
any code is written. It records what the law demands, what eTIMS demands of a
till specifically, the four ways in, the one I recommend, and the questions that
must be answered first.

Everything about Etham's current state below was read off the live site on
7 September 2026. Everything about KRA's requirements carries a source at the
end; those must be re-verified against KRA's own documents on the day work
starts, because the rules have moved repeatedly since 2023.

---

## 0. The decision that comes before the code

**Etham charges no VAT today.** On the live site:

| What | State on 7 Sep 2026 |
|---|---|
| Company KRA PIN (`Company.tax_id`) | not set |
| VAT on submitted invoices | `0.00` on every one |
| Sales tax template `Kenya Tax - ETH` | exists, 16% on net, VAT-**exclusive**, not default |
| POS Profile `taxes_and_charges` | not set, so the template never applies |
| Items carrying an item tax template | 0 of 179 |
| Customers with a PIN recorded | 0 of 11 |

eTIMS transmits what you invoice. Wire it up tomorrow and it would faithfully
report zero-VAT invoices, which fixes nothing and creates a signed record of the
under-charging. So the first phase is not technical:

1. **Is Etham VAT registered, and from when?** The PIN and the effective date
   decide whether this is a compliance project or a nice-to-have. Note that the
   2024 regulations reach beyond VAT registration (§1), so eTIMS may apply even
   if VAT does not.
2. **Are menu prices VAT-inclusive or VAT-exclusive?** The existing template is
   exclusive, which would add 16% on top of every price on the menu. Inclusive
   means Etham absorbs roughly 13.8% of current takings instead. That is a
   pricing decision with a real revenue effect, and it is the client's to make,
   not ours.
3. **Which supplies are standard-rated?** Prepared food and restaurant service
   are normally standard-rated; some packaged goods and water may differ. This
   needs a line-by-line pass over the menu with whoever does Etham's tax.

Nothing in phases 1 onward is safe to build until those three are answered,
because they determine the tax classification carried on every transmitted line.

---

## 1. What the law requires

Under the Tax Procedures (Electronic Tax Invoice) Regulations 2024, every person
carrying on business in Kenya must generate and transmit invoices electronically
through eTIMS, whether or not they are VAT registered, for business invoices
above KES 100. Exemptions are narrow and do not cover a restaurant.

Failure to issue an eTIMS invoice for a taxable supply attracts a penalty of
twice the tax due on that supply, subject to a minimum of KES 100,000, with
wider Tax Procedures Act penalties reaching KES 1,000,000 or imprisonment.
Enforcement has tightened each year since 2024.

**Read this as: not optional, and the downside is not a fine we can absorb
quietly.** It is also a reason not to rush: a half-integration that transmits
wrong tax classifications is worse than a documented, dated plan to integrate.

---

## 2. What eTIMS demands of a till

An eTIMS tax invoice must carry, at minimum: the seller's PIN, the buyer's PIN
where the buyer will claim input tax, a unique serial invoice number, the date
and time of issue, per-line item code, description, quantity, unit, tax rate,
the gross and tax amounts, and **the control number and QR code that KRA returns
when the invoice is transmitted**.

That last clause is the whole problem for a point of sale. Without the control
number and QR, what the customer holds is a receipt, not a compliant tax
invoice. Our till prints the receipt the instant payment is confirmed, from a
hidden frame in the same tab. So either

- the invoice is transmitted and acknowledged **before** the receipt prints, and
  the till now waits on KRA for every sale, or
- the invoice is signed **locally** by a control unit on our side, and the
  acknowledged copy follows asynchronously.

Which of those is available depends entirely on the path chosen in §3. It is the
single most consequential decision in this document.

Beyond the invoice itself, eTIMS expects:

- **Items registered and classified before sale.** Every menu item needs a KRA
  classification code and a registration call. An unregistered item cannot
  lawfully be sold.
- **Credit notes** referencing the original invoice, for anything cancelled or
  refunded.
- **Stock movement reporting**, on the control-unit paths.
- **A per-branch identity**: the communication key is derived from the company
  PIN, a branch ID and a device serial number, and KRA issues it once.

---

## 3. The four ways in

| Path | What it is | Fit for this kit | Certification |
|---|---|---|---|
| **eTIMS Lite** | KRA's web portal, invoices keyed by hand | None. A busy service cannot key invoices into a browser | Not needed |
| **OSCU, self-integrated** | Our code calls KRA's API per invoice; the control unit lives at KRA and requires the till to be online for every sale | Possible, but couples every payment to KRA's uptime and to a Nairobi→Europe→KRA round trip | We must be vetted and certified by KRA |
| **VSCU, self-integrated** | KRA's control-unit package runs on our side, signs locally, uploads in bulk; built for high volume and imperfect connectivity | Architecturally the best fit: local signing lets the receipt print immediately | We must be vetted and certified by KRA |
| **Approved third-party middleware** | An integrator already certified by KRA (for example Slade360 / Savannah Informatics) sits between us and eTIMS, over VSCU | Fastest to live, and an ERPNext app for this path already exists and is actively developed | Theirs, not ours |

### Recommendation

**Start on the third-party middleware path, and keep VSCU self-integration as
the fallback.** Three reasons:

1. It takes KRA certification off our critical path. Certification lead time is
   entirely outside our control and would otherwise gate the whole project.
2. `navariltd/kenya-compliance-via-slade` already integrates ERPNext with eTIMS
   over that route and is under active development. Its sibling for direct OSCU,
   `navariltd/kenya-compliance`, is explicitly no longer maintained, which is a
   strong signal about which route survives.
3. Middleware fees are a per-site running cost we can price into the product,
   whereas certification is a one-off cost we cannot schedule.

The fallback matters because the middleware becomes a dependency in the payment
path and a recurring cost per restaurant. If either turns out unacceptable at
scale, VSCU self-integration is the same architecture without the intermediary.

### How this app came to our attention

`overrides/apps.txt` on the server turned out to be shell history pasted into a
file by mistake, and it contained a URL for `kenya-compliance-via-slade`. Nothing
referenced it and the app was never installed. Worth knowing so nobody mistakes
that line for a decision already taken.

### What must be evaluated before committing

The existing app is a candidate, not a decision. Before adopting it:

- **Version fit.** The Slade app carries a `version-16` branch at tag `16.5.2`,
  which is why it is the candidate; we run frappe 16.31.0 and ERPNext 16.32.3, so
  confirm that tag against those two rather than trusting the branch name. The
  direct OSCU app states no version support at all.
- **POS Invoice coverage.** Our sales are POS Invoices submitted at payment and
  consolidated at day close. An app built around Sales Invoice submission may
  transmit at the wrong moment, or twice.
- **Credit notes.** Not mentioned in the OSCU app's documentation. Verify in the
  Slade app's code.
- **Patch-layer coexistence.** We already patch `table_order.py`'s
  `make_invoice`. Another app hooking the same submission needs its order of
  operations pinned down, and our patches must anchor on source it does not move.

If the app fits, we contribute our restaurant-specific pieces upstream rather
than forking it. If it does not, we write a thin app of our own against the same
middleware API and keep the surface small.

---

## 4. Where it lands in this architecture

### The tax invoice is the POS Invoice, not the day-close consolidation

A guest pays, `TableOrder.make_invoice` submits a POS Invoice, the receipt
prints. At close of day those POS Invoices consolidate into Sales Invoices. The
document the customer is handed is the POS Invoice, so **that** is the tax
invoice and that is what must be transmitted. Transmitting the consolidated
Sales Invoice instead would report one invoice per day with no customer detail,
which is not what the customer holds in their hand.

### The receipt and the control number

This is the crux from §2, and it is where our own latency work matters. The
server is in France, the restaurant in Nairobi: 300 to 600 ms per API call
before KRA is involved at all. A synchronous KRA hop inside the payment path
adds to that and makes every sale dependent on KRA being up.

The design I would build, subject to confirming it is lawful:

1. Payment submits the POS Invoice and enqueues the transmission.
2. Local signing (VSCU, ours or the middleware's) yields the control data
   immediately, so the receipt prints complete, exactly as it does now.
3. If the control data cannot be obtained at all, the receipt prints marked as
   pending, the invoice stays queued, and the compliant copy is available from
   the invoice as soon as KRA acknowledges it. The till never blocks on KRA.
4. A background job drains the queue and a report shows anything unacknowledged,
   so nothing silently fails to reach KRA.

**Step 3 needs a definitive answer from KRA or the integrator before it is
built.** If a receipt may never be handed over without a control number, then
the fallback is not "print pending" but "the till cannot complete the sale", and
the offline story changes completely. Do not guess this one.

### Item registration meets the menu

We already learned that a dish must be non-stock to be sellable (finding 30), and
that rule is enforced when a dish joins the menu. eTIMS adds a second condition
at the same seam: a dish must be **classified and registered with KRA** before
it can be sold. That belongs in the same hook, `house.menu_sells_without_stock`'s
neighbour, with the Menu Management editor showing registration state on the
card and refusing to publish an unclassified dish. All 179 items on the menu today need a
classification pass and a UOM mapping, which is the client's data task, like
recipes — and after registration it is the longest pole in the project.

### The pieces that need rework

| Piece | Today | Under eTIMS |
|---|---|---|
| `Etham Receipt` print format | 80 mm thermal, payment rows with M-Pesa codes | adds seller PIN, buyer PIN, per-line tax rate, tax summary, control number and a QR code that must render in the hidden-frame print path |
| Cancelling a sale | Cancel the POS Invoice | must also transmit a credit note against the original control number; the admin guide's wording changes |
| Delivery fee | an Actual tax row booked to Delivery Charges | probably a classified line item, since a charge row has no item code or tax type |
| Split M-Pesa payments | several payment rows, one per confirmation code | map to eTIMS payment types; verify several rows of one mode are accepted |
| `Walk-in Guest` default customer | no PIN, fine today | B2B guests who want to claim input tax need their PIN captured at the till |

### The constraint on multi-tenant

eTIMS credentials are per taxpayer: PIN, branch ID and device serial produce one
communication key, issued once. In a multi-tenant deployment these must live
**per site or per company and never in a shared configuration**. Getting this
wrong would transmit one restaurant's sales under another's PIN, which is the
worst failure mode in this document.

This is a good reason to do the multi-tenant work first, as planned: it is much
easier to design per-tenant credential isolation into a multi-tenant deployment
than to retrofit it after eTIMS assumes a single taxpayer.

---

## 5. Phasing

**Phase 0. Tax position.** The three questions in §0, answered by the client and
their tax adviser. Output: PIN on the company, a decision on inclusive versus
exclusive pricing, and a per-item tax classification list. No code.

**Phase 0b. Registration, which is the real blocker.** Before a line of code
matters: Etham (or we on their behalf) registers for KRA and VSCU, which the
vendor runs — `etims@savannahinformatics.com`; a Slade 360 Advantage account and
credentials exist; and the company PIN, branch ID and device details are recorded
against the ERPNext company. Treat this as **lead time in weeks, not a sprint**.
Nothing can be tested end to end until sandbox credentials exist, so this starts
the day Phase 0 is answered.

**Phase 1. Sandbox spike.** Against `etims-sbx.kra.go.ke` or the integrator's
sandbox. Prove exactly one thing end to end: a POS Invoice from the till is
transmitted, comes back with a control number and QR, and the thermal receipt
prints carrying both. This also settles the version-fit question in §3. Output:
a go or no-go on the existing app.

**Phase 2. Items.** Classification codes on all 179 items, registration calls,
registration state visible in Menu Management, and a dish that is not registered
cannot be published to the menu.

**Phase 3. The till path.** The queue, the offline rule from §4 (as confirmed,
not as assumed), credit notes on cancel, the delivery fee rework, buyer PIN
capture, and the unacknowledged-invoice report.

**Phase 3b. Ship it the way everything else ships.** Add the app to
`apps-restaurant.json` **pinned to a tag**, record it in `restaurant/PINNED_APPS`,
and rebuild the base with `CACHE_BUST` — editing that JSON alone does not bust the
build cache (iron rule 8). Then check the patch layer for collisions: we already
patch `table_order.py`, `pay-form-class.js` and POS Invoice custom fields, all of
which this app also touches. Deploy behind the usual gate: build locally, verify
inside the image, ship, migrate.

**Phase 4. Certification.** Whatever the chosen path demands: the integrator's
onboarding, or KRA vetting if we self-integrate. Lead time is outside our
control, so it starts as early as the path allows.

**Phase 5. Pilot then spread.** One branch live, watched for a full week of
service against the M-Pesa and closing figures, before any second site.

---

## 6. Testing, which we do not cut

The deep suites are what keep bugs off the live floor, and eTIMS gets the same
treatment. Against the sandbox only, never production eTIMS:

- a paid POS Invoice comes back with a control number, and the receipt carries it
- an unregistered dish cannot be published to the menu, and cannot be sold
- cancelling a sale transmits a credit note referencing the original
- an invoice transmitted while the link is down is queued, and drains later, and
  the unacknowledged report shows it until it does
- a bill split across several M-Pesa transactions reports every payment
- a delivery with its fee reports the fee correctly classified
- per-tenant credentials: two companies on one deployment never borrow each
  other's PIN
- **the network blackholed mid-service**: a sale still completes, and submission
  never blocks `POS Invoice.submit()`

The last two are worth writing before the code they guard, and the blackhole test
runs before this goes anywhere near a Friday service.

---

## 7. Risks

- **KRA or middleware downtime stops sales**, if the lawful answer to §4 step 3
  is that no receipt may be issued without a control number. Mitigation is a
  documented manual fallback agreed with the client in advance, not code.
- **Certification lead time** is not ours to schedule. The middleware path exists
  precisely to move this off the critical path.
- **The maintained app is a dependency on one vendor**, both for code and for the
  middleware itself. The fallback in §3 is the answer, and it should stay warm.
- **Menu items created during service.** Our editor can add a dish mid-shift;
  under eTIMS such a dish is unsellable until registered. The seam must fail
  loudly at publish time, not quietly at payment.
- **A price change is a client-facing event.** If VAT becomes exclusive, every
  menu price moves. That is a business decision needing lead time, printed menus
  and staff briefing.
- **Wrong classification transmitted at scale** is worse than late integration.
  This is the reason for Phase 0.

---

## 8. Open questions

Nothing in phases 1 onward should start until these are answered.

1. Is Etham VAT registered, with what PIN, effective when? — client
2. Inclusive or exclusive pricing, and who absorbs the 16%? — client
3. Tax classification per menu item. — client's tax adviser, with our export
4. **May a receipt be handed to a customer before KRA returns a control number,
   if the compliant invoice follows?** — KRA or the integrator, in writing
5. Middleware pricing per site per month, and its uptime commitment. — integrator
6. Does the chosen app support POS Invoice submission and credit notes on
   frappe 16.31 / ERPNext 16.32? — our Phase 1 spike
7. Branch and device identity for a multi-site future: one PIN with several
   branch IDs, or separate taxpayers? — client, then KRA
8. Who holds the communication key, and what is the recovery path if it is lost?
   KRA issues it once. — client and integrator

---

## 9. Honest estimate

Integration and its tests: a few days of our work, once credentials exist.
Registration and the item classification pass: unknown, because both are driven
by KRA and by Etham rather than by us. The order of magnitude is weeks of waiting
around a few days of building, which is why Phase 0 and Phase 0b start long
before anything is coded.

---

## Sources

Re-verify all of these before work starts; the rules have changed repeatedly.

- KRA, eTIMS system-to-system integration (OSCU and VSCU, sandbox, certification):
  <https://www.kra.go.ke/business/etims-electronic-tax-invoice-management-system/learn-about-etims/etims-system-to-system-integration>
- KRA, OSCU and VSCU step-by-step sign-up guide:
  <https://www.kra.go.ke/images/publications/OSCU_VSCU_Step-by-Step_Guide-on-how-to-sign-up.pdf>
- KRA eTIMS taxpayer portal: <https://etims.kra.go.ke/> — sandbox at <https://etims-sbx.kra.go.ke/>
- Navari, ERPNext eTIMS over OSCU (no longer actively developed):
  <https://github.com/navariltd/kenya-compliance>
- Navari, ERPNext eTIMS over Slade360 / VSCU (active):
  <https://github.com/navariltd/kenya-compliance-via-slade>
- Invoice field and control-number requirements:
  <https://veirahq.com/blog/etims-invoice-requirements/>
- Regulations, thresholds and penalties:
  <https://www.amgadvocates.com/post/vat-registration-and-compliance-in-kenya-complete-guide-to-etims-registration-threshold-and-kra-s>
