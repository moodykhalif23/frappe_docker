# Opening a shared table's pad selected nothing: Complete answered "Not order
# Selected" and only a dish-tap ever asked whose check it was. The pad now opens
# on the check the waiter just created, selects a lone check itself, and only
# asks when it genuinely cannot tell.
P = "apps/restaurant_management/restaurant_management/public/restaurant/js/order-manage-class.js"

src = open(P).read()

PREFER = """        // The waiter who just seated this party gets their check, no question.
        const wanted = RM.navigate_order;
        if (wanted) {
          RM.navigate_order = null;
          const mine = this.get_order && this.get_order(wanted);
          if (mine) return mine.select();
        }
"""

if "rm_pick_on_open" in src:
    changed = []
    # an earlier bake shipped a DOM guard that the pad's own modal always trips
    BAD = ' && !document.querySelector(".modal.show")'
    if BAD in src:
        src = src.replace(BAD, "", 1)
        changed.append("dropped the self-defeating modal guard")
    if "RM.navigate_order" not in src:
        OLD_BODY = """        if (this.current_order) return;
        if (this.child_count === 1) return this.select_last_order();"""
        NEW_BODY = """        if (this.current_order) return;
""" + PREFER + """        if (this.child_count === 1) return this.select_last_order();"""
        if OLD_BODY not in src:
            raise SystemExit("pad pick: cannot upgrade, on-open body not found")
        src = src.replace(OLD_BODY, NEW_BODY, 1)
        changed.append("opens on the check just seated")
    if changed:
        open(P, "w").write(src)
        print("pad pick: " + "; ".join(changed))
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
""" + PREFER + """        if (this.child_count === 1) return this.select_last_order();
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
