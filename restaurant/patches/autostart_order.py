# First tap on a dish opens the check. Without this, add_item_in_order() runs its
# `if (current_order != null)` guard, falls through and does nothing at all.
P = "apps/restaurant_management/restaurant_management/public/restaurant/js/product-item-class.js"

src = open(P).read()
if "__party_check" in src:
    print("auto-start order: already applied")
    raise SystemExit

ANCHOR = """    const current_order = this.order_manage.current_order;
    const pos_profile = RM.pos_profile;

    if (current_order != null) {"""

BLOCK = """    const current_order = this.order_manage.current_order;
    const pos_profile = RM.pos_profile;

    // No check selected: on a shared table there may already be one per party,
    // and opening another would bill the same guests twice.
    if (current_order == null) {
      const om = this.order_manage;
      if (om.__starting_order) return;
      om.__party_check = true;

      if (window.RM_seats && RM_seats.pick_check(om, () => this.add_item_in_order(item, qty))) return;

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

# An earlier bake opened a second check on every tap; replace that block whole.
start = src.find("    // No check open on this table yet")
if start != -1:
    end = src.find("    if (current_order != null) {", start)
    if end == -1:
        raise SystemExit("auto-start order: cannot find the end of the old block")
    src = src[:src.rfind("    const current_order = this.order_manage.current_order;", 0, start)] + BLOCK + src[end + len("    if (current_order != null) {"):]
    open(P, "w").write(src)
    print("auto-start order: upgraded to pick a party's check")
    raise SystemExit

if ANCHOR not in src:
    raise SystemExit("auto-start order: anchor not found — add_item_in_order changed upstream")

open(P, "w").write(src.replace(ANCHOR, BLOCK, 1))
print("auto-start order: applied")
