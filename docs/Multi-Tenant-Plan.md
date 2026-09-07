# Multi-tenant: one deployment, many restaurants

The kit currently runs one restaurant per server. The goal is many restaurants on
one deployment, so that onboarding the tenth costs a command rather than a
server. This is the highest-value piece of work left, because it turns a bespoke
install into a product.

The good news, established by reading the stack rather than guessing: **most of
this already works.** frappe is multi-site by design, our image is shared, and
our patch layer derives company details rather than hardcoding them. What stands
in the way is one pinned environment variable, four hardcoded strings, and a set
of operational questions nobody has had to answer yet.

State below was read off the live server on 7 September 2026.

---

## 1. The model: a site per restaurant

frappe offers two ways to host several businesses. They are not equally good
here.

| | **Site per restaurant** (recommended) | Company per restaurant, one site |
|---|---|---|
| Isolation | separate database each | one shared database |
| Our fork's assumptions | hold unchanged | every "the default company" and "the enabled POS profile" lookup becomes a bug |
| A tenant's own domain | natural, and required by iron rule 3 | impossible, everyone shares one URL |
| Backup and restore for one client | one command | extract rows from a shared database |
| Deleting a client | drop a database | delete rows and hope |
| eTIMS credentials per taxpayer | naturally isolated | one field, many taxpayers, worst failure in the eTIMS plan |
| Effort | small, mostly operational | large, and every future patch must stay company-aware |

**Site per restaurant.** One bench, one image, one MariaDB, one Redis, one set of
workers, and a database per tenant. That is also how frappe_docker is built to
run, so we are going with the grain rather than against it.

The rejected option is worth stating plainly because it looks cheaper and is not:
our floor code asks for `frappe.defaults.get_global_default("company")` and for
"the POS profile that is not disabled". Those are correct statements about a
restaurant. In a shared database they become guesses, and every patch we have
written would need re-auditing for company awareness. That is a large, permanent
tax for no benefit.

---

## 2. What already works

- **The image is shared.** `custom-erpnext:v16.32.3` carries the app and all 64
  patches. One bake serves every tenant. This is the flex: restaurant N+1 gets
  every fix and feature at once.
- **The frontend already routes by hostname.** `compose.yaml` sets
  `FRAPPE_SITE_NAME_HEADER: ${FRAPPE_SITE_NAME_HEADER:-$$host}`. Left unset, each
  request resolves to the site matching its own `Host` header. Multi-site routing
  is not something we build; it is something we stop overriding.
- **Iron rule 3 is satisfied for free.** The rule says a site's name must equal
  its public domain, because nginx rewrites `Origin` to the site name and the
  websocket auth requires `Host == Origin`. Under hostname routing each tenant's
  requests carry their own domain, so the rule holds per tenant automatically.
- **Company details are derived, not hardcoded.** The delivery account is built
  from `Company.abbr` at runtime, the delivery charge record is per company, and
  `demo_seed.py` discovers or creates the company rather than assuming one. So a
  second site gets its own accounts with its own abbreviation, unprompted.
- **Marginal cost per tenant is a database, not a stack.** After two and a half
  weeks of real service Etham's database is **63 MB**. Adding a site adds no
  containers: the same gunicorn, queues, scheduler and websocket serve all of
  them.

---

## 3. What stands in the way

### One pinned variable

`.env` on the server holds `FRAPPE_SITE_NAME_HEADER=frappe.ikobriq.com`. That
pins every request to one site regardless of the domain it arrived on. Unsetting
it restores hostname routing. **This is the change that makes the whole thing
possible, and it must be made and tested with a second site present, not before,
or the running restaurant is the one that breaks.**

### Four hardcoded strings

The only client-specific text baked into the patch layer is the names of two
print formats: `Etham Receipt` and `Etham Order Bill`, in `house.py` and
`print_ticket.py`. Every tenant would get formats carrying another restaurant's
name. These become generic (`RM Receipt`, `RM Order Bill`) or per-site, and the
existing live formats are renamed once so Etham keeps working.

### Assumptions to audit before the second tenant, not after

Each of these is correct for one restaurant per site and should stay that way.
The audit is to confirm each is per-site rather than per-installation:

- `POS Profile` where `disabled = 0` — one profile per site. Fine, but a site
  with two profiles (two branches of one restaurant) would pick arbitrarily.
- `frappe.defaults.get_global_default("company")` — per site, so fine.
- `Restaurant Settings` — a Single doctype, one per site, so fine.
- The bake id in `window.RM_BUILD` and the versioned includes — per image, shared
  deliberately.
- Waiter PINs, the delivery fee, the recheck window, the delivery room — all
  per-site records already.

### The operational gaps

These are the real work, and they are not code in the app:

1. **DNS and TLS per tenant.** Each restaurant needs its own domain pointed at
   the box and a certificate. Caddy fronts the stack (a 167-line Caddyfile) and
   can issue certificates automatically, so this becomes an entry per tenant.
2. **Name resolution from inside the containers.** The websocket service
   authenticates each socket by fetching `http://<site name>/api/...`. Every new
   tenant domain must therefore resolve *from inside that container*, which is
   why the localhost override exists for development and must never be used in
   production (iron rule 3).
3. **Backups per tenant**, with a restore that touches one restaurant and not the
   others.
4. **An onboarding command**, so adding a restaurant is one repeatable operation
   rather than a remembered sequence.

---

## 4. Onboarding a restaurant

`deploy.sh` already does the per-site work and is re-runnable: it creates the
site with `bench new-site --install-app erpnext --install-app restaurant_management`,
migrates, sets `host_name`, enables the scheduler, then seeds. It takes `SITE`
from the environment. So the onboarding path is mostly a wrapper that adds what
`deploy.sh` does not:

```
restaurant/add-restaurant.sh
  SITE=pos.client.co.ke
  COMPANY="Client Name"       ADMIN_PASSWORD=...
  1. refuse if the site exists, or if the domain does not resolve to this box
  2. bench new-site + install apps + migrate            (deploy.sh does this)
  3. seed: company, POS profile, menu skeleton, rooms, roles, print formats
  4. create the manager user and print the credentials once
  5. add the Caddy entry, reload Caddy, wait for the certificate
  6. verify: the floor loads over https, the socket connects, a test seat and
     release succeed, then remove the test data
  7. record the tenant in a register (domain, company, created, contact)
```

Step 6 is the part that must not be skipped. A restaurant that is created but
whose websocket does not authenticate looks fine until the first busy service.

Step 3 is where the product decision sits: what does a **new** restaurant start
with? Etham's site was seeded with a demo menu and then reworked. A new tenant
should start with rooms, roles, print formats and an *empty* menu, plus the
import path for their own dishes. Seeding someone else's dishes is worse than
seeding nothing.

---

## 5. Capacity

What the numbers say about the current box (4 CPUs, 7 GB RAM with 3 GB in use,
145 GB disk with 56 GB free, shared with several unrelated services):

| Resource | Per tenant | Comment |
|---|---|---|
| Database | ~63 MB after 2.5 weeks | disk is not the constraint |
| Containers | none | the same workers serve every site |
| RAM | small, mostly Redis and connections | the frappe stack totals about 1 GB today |
| CPU | per concurrent till, not per tenant | this is the real constraint |

The limit is therefore **concurrent tills at peak**, not the number of
restaurants. Every screen polls occupancy every 15 seconds and each call costs
the server 15 to 40 ms, so the arithmetic is tractable: measure it rather than
guess it, with a load probe standing in for N tills before selling the N+1th
restaurant. That probe does not exist yet and belongs in this project.

An honest caveat: this box is shared with unrelated services and has 4 CPUs. It
is fine for a handful of restaurants and it is not where twenty should live. The
sizing question and the region question (Nairobi rather than France, which would
halve every round trip) belong together.

---

## 6. The blast radius, which is the cost of the flex

One image serves every tenant. A good bake improves every restaurant at once,
and **a bad bake breaks every restaurant at once.** Today a bad deploy affects
one client who knows us; with ten tenants it is an incident.

So multi-tenant changes the release process, not just the topology:

1. The fourteen suites stay exactly as they are, and gate every bake. They are
   the reason bugs are found before production and that does not change.
2. **Staged rollout.** A canary tenant (our own, or Etham with their agreement)
   takes the image first, runs a service, and only then does it reach the rest.
   That requires the ability to pin a tenant to an image version, which the
   single-image model does not currently allow. Solving it means either two
   benches (canary and fleet) or accepting a canary window on one.
3. **A rollback that is one command**, tested, because with ten tenants the
   pressure to fix forward will be wrong more often than it is right.
4. **A status page or health probe per tenant**, so we learn about a broken site
   from monitoring rather than from a phone call during dinner service.

Point 2 is the genuinely hard one and it should be decided before the second
tenant, not after the fifth.

---

## 7. Data isolation, proved rather than assumed

Separate databases give isolation by construction, but the things that leak are
the things that are not in the database: shared caches, shared assets, and any
code path that resolves a site from something other than the request.

The suite to write, and to keep:

- two sites on one deployment, each with its own company, menu and waiters
- a floor loaded on site A never shows site B's tables, and its API calls
  refuse a table name belonging to B
- a waiter PIN valid on A is rejected on B
- Redis-cached page scripts and boot info do not cross sites
- a report on A totals only A's sales
- restoring A's backup leaves B untouched
- a socket connected to A receives none of B's realtime events

The last one is worth writing first, because realtime is the layer that took the
longest to get right for one tenant and it publishes on channels named after
documents.

---

## 8. Phasing

**Phase 1. Local proof.** Two sites on the development stack, hostname routed,
with the isolation suite from §7 passing. No production change. This is where the
pinned-variable question and the print-format renaming are settled.

**Phase 2. Onboarding command.** `add-restaurant.sh` per §4, exercised by
creating and destroying a throwaway tenant locally several times, ending with the
verification step and the tenant register.

**Phase 3. Production switch, with Etham protected.** Unpin the variable on the
server with Etham as the only site, confirm nothing changes for them, and only
then add a second site. Etham's continuity is the acceptance criterion for this
phase, not the second site working.

**Phase 4. Release process.** Staged rollout, rollback, per-tenant health checks,
and the load probe from §5. This phase is what makes it safe to sell.

**Phase 5. Second real tenant**, treated as a pilot with the same care Etham got:
one service watched end to end before a third.

---

## 9. Risks

- **Unpinning the site header on a live server** is the sharpest moment in the
  plan. Wrong, and Etham's floor stops resolving. Mitigation: Phase 3 does it
  with one site present so the change is provably neutral before any tenant is
  added.
- **One bad bake now hits everyone.** §6 is the whole answer, and it is not
  optional past the second tenant.
- **A shared 4-CPU box** limits how far this goes. Measure with the load probe
  before selling capacity that has not been demonstrated.
- **Websocket auth per domain** is the failure that hides until service. It goes
  in the onboarding verification step, not in a checklist someone remembers.
- **Cross-tenant configuration creeping in.** Any future setting added as a
  single global value becomes a leak. The eTIMS credentials are the sharpest
  example and the eTIMS plan already carries that constraint.
- **Support load, not technical.** Ten restaurants means ten sets of staff who
  can lock themselves out at 8pm on a Friday. Worth pricing before selling.

---

## 10. Open questions

1. How many restaurants is this actually for in the next year? Three changes
   none of the above; thirty changes the hosting decision.
2. Same box, or a dedicated box for the fleet? Related: Nairobi rather than
   France, which halves the round trip that is currently the biggest latency
   cost.
3. One domain per tenant on their own name (`pos.client.co.ke`), or subdomains of
   ours (`client.ikobriq.com`)? Ours is faster to onboard and easier to certify.
4. Canary tenant: our own demo instance, or Etham with their agreement?
5. What does a new restaurant start with — an empty menu and an import, or a
   template menu they edit?
6. Who holds a tenant's admin credentials, and what is the reset path?
7. Is a tenant's data theirs to export on request, and in what format? Worth
   answering before it is asked.

---

## Cross-references

- `CLAUDE.md` iron rule 3 is the constraint that shapes all of this.
- `docs/eTIMS-Integration-Plan.md` §4 carries the per-tenant credential
  constraint, which is a reason to do this work first.
- `restaurant/deploy.sh` already performs the per-site work an onboarding
  command wraps.
