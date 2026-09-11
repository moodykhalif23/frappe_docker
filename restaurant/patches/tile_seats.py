# The third door. Tapping an empty table opened the pad straight onto a customer box,
# so a check could start with no waiter and no covers — the two things the floor is for.
P = ("apps/restaurant_management/restaurant_management/public/restaurant/js/"
     "restaurant-object-class.js")

src = open(P).read()
if "rm_tile_seats" in src:
    print("tile seats: already applied")
    raise SystemExit

OLD = """      const _open = () => {
        if (this.order_manage == null) {"""

NEW = """      const _open = () => {
        // rm_tile_seats: an empty table is seated through the door — PIN, waiter,
        // covers — before a check exists. A table already holding one opens as before.
        if (window.RM_host_stand && RM_host_stand.open_for && !this.__rm_seating
            && !RM.transfer_order) {
          const occ = window.RM_seats && RM_seats.seats && RM_seats.seats(this.data.name);
          const parties = occ && occ.parties ? occ.parties.length : 0;
          if (!parties && !(this.data.orders_count > 0)) {
            this.__rm_seating = true;
            setTimeout(() => { this.__rm_seating = false; }, 30000);
            RM_host_stand.open_for(this.data.name, null, () => { this.__rm_seating = false; });
            return;
          }
        }
        if (this.order_manage == null) {"""

if src.count(OLD) != 1:
    raise SystemExit("tile seats: open anchor found %d times" % src.count(OLD))

open(P, "w").write(src.replace(OLD, NEW, 1))
print("tile seats: an empty table seats a party before opening a check")
