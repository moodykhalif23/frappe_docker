# First tap on a dish opens the check. Without this, add_item_in_order() runs its
# `if (current_order != null)` guard, falls through and does nothing at all — no
# message, no disabled button, just a dead tap.
P = "apps/restaurant_management/restaurant_management/public/restaurant/js/product-item-class.js"

src = open(P).read()
if "__starting_order" in src:
    print("auto-start order: already applied")
    raise SystemExit

ANCHOR = """    const current_order = this.order_manage.current_order;
    const pos_profile = RM.pos_profile;

    if (current_order != null) {"""

BLOCK = """    const current_order = this.order_manage.current_order;
    const pos_profile = RM.pos_profile;

    // No check open on this table yet: start one, wait for it to be selected,
    // then add the dish. Tapping a dish is how a server opens a check.
    if (current_order == null) {
      const om = this.order_manage;
      if (om.__starting_order) return;
      om.__starting_order = true;
      om.add_order();

      let tries = 0;
      const waiting = setInterval(() => {
        tries += 1;
        if (!om.current_order && om.last_order) om.select_last_order();

        if (om.current_order) {
          clearInterval(waiting);
          om.__starting_order = false;
          this.add_item_in_order(item, qty);
        } else if (tries > 40) {
          clearInterval(waiting);
          om.__starting_order = false;
          RM.notification("red", __("Could not start an order for this table"));
        }
      }, 200);
      return;
    }

    if (current_order != null) {"""

if ANCHOR not in src:
    raise SystemExit("auto-start order: anchor not found — add_item_in_order changed upstream")

open(P, "w").write(src.replace(ANCHOR, BLOCK, 1))
print("auto-start order: applied")
