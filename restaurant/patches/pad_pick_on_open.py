# Opening a shared table's pad selected nothing: Complete answered "Not order
# Selected" and only a dish-tap ever asked whose check it was. The pad now asks
# on open when several checks live there, and selects the one check itself.
P = "apps/restaurant_management/restaurant_management/public/restaurant/js/order-manage-class.js"

src = open(P).read()
if "rm_pick_on_open" in src:
    # an earlier bake shipped a DOM guard that the pad's own modal always trips
    BAD = ' && !document.querySelector(".modal.show")'
    if BAD in src:
        open(P, "w").write(src.replace(BAD, "", 1))
        print("pad pick: dropped the self-defeating modal guard")
    else:
        print("pad pick: already applied")
    raise SystemExit

OLD = """    RM.is_mobile && this.select_last_order();
  }"""
NEW = """    RM.is_mobile && this.select_last_order();

    // rm_pick_on_open: a lone check selects itself; several ask whose it is.
    if (!RM.is_mobile && !this.current_order) {
      setTimeout(() => {
        if (this.current_order) return;
        if (this.child_count === 1) return this.select_last_order();
        if (this.child_count > 1 && window.RM_seats) {
          RM_seats.pick_check(this, () => {});
        }
      }, 600);
    }
  }"""

if src.count(OLD) != 1:
    raise SystemExit("pad pick: expected exactly one anchor, found %d" % src.count(OLD))
open(P, "w").write(src.replace(OLD, NEW, 1))
print("pad pick: the pad asks on open")
