# Two doors around the seating rule: the pad's + created another check on the
# table with no party, no covers and no PIN, and a dish tapped with no check
# selected did the same. Both now go through Seat guest, locked to this table.
# A dish tapped while a party's checks have simply not loaded yet picks that
# party's check instead of seating a new one.
OM = "apps/restaurant_management/restaurant_management/public/restaurant/js/order-manage-class.js"
PI = "apps/restaurant_management/restaurant_management/public/restaurant/js/product-item-class.js"

src = open(OM).read()
if "rm_pad_plus_seats" in src:
    print("pad plus: already applied")
else:
    OLD = """    }).on("click", () => {
      this.add_order();
    }, !RM.restrictions.to_new_order ? DOUBLE_CLICK : null);
"""
    NEW = """    }).on("click", () => {
      // rm_pad_plus_seats: another party at this table — PIN, covers, seats left
      if (window.RM_host_stand && RM_host_stand.open_for) return RM_host_stand.open_for(this.table.data.name, this);
      this.add_order();
    });
"""
    if src.count(OLD) != 1:
        raise SystemExit("pad plus: new-order button anchor found %d times" % src.count(OLD))
    open(OM, "w").write(src.replace(OLD, NEW, 1))
    print("pad plus: the + seats a party through Seat guest")

NEW_DISH = """      // rm_pad_plus_seats: no check selected — a party already here means the
      // checks have not loaded yet (pick one); an empty table seats a party first
      if (window.RM_host_stand && RM_host_stand.seat_or_pick) {
        om.__party_check = false;
        RM_host_stand.seat_or_pick(om, () => this.add_item_in_order(item, qty));
        return;
      }
"""
EARLIER = """      // rm_pad_plus_seats: no check and no party here — seat one first, then add the dish
      if (window.RM_host_stand && RM_host_stand.open_for) {
        om.__party_check = false;
        RM_host_stand.open_for(om.table.data.name, om, () => this.add_item_in_order(item, qty));
        return;
      }
"""
UPSTREAM = """      om.__starting_order = true;
      om.add_order();
"""

src = open(PI).read()
if EARLIER in src:
    open(PI, "w").write(src.replace(EARLIER, NEW_DISH, 1))
    print("dish tap: upgraded — a loaded party is picked, not re-seated")
elif "rm_pad_plus_seats" in src:
    print("dish tap: already applied")
else:
    if src.count(UPSTREAM) != 1:
        raise SystemExit("dish tap: add_order anchor found %d times" % src.count(UPSTREAM))
    open(PI, "w").write(src.replace(UPSTREAM, NEW_DISH + UPSTREAM, 1))
    print("dish tap: a dish with no check picks the party's check or seats one")
