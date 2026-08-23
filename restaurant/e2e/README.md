# Browser test

`flow.mjs` drives the whole pass in a real browser: sign in, load the floor,
sign a waiter on with a PIN, seat a walk-in, open the pad, create and select an
order, ring up a dish, dispatch it, check the tile badge, then re-check the
floor at tablet and phone widths. It screenshots every step into `shots/`.

```bash
npm i playwright@1.62.1
BASE=https://pos.example.com USER_=Administrator PASS=... \
  WAITER="Amina Otieno" PIN=4821 GUEST="Test Party" node flow.mjs
```

It writes real records. Run it against a demo site, or delete the guest's
booking, order and customer afterwards.

**Why this exists.** Four defects shipped past a full API-level suite and were
only caught here: an appended IIFE parsed as a call and blanked the floor; a
`?v=` cache-buster broke frappe's asset loader; `set_route` with a query string
raised "Page not found"; and a seated table had no customer, so the pad refused
to open an order. `node --check` and green server tests say nothing about
whether the page runs.
