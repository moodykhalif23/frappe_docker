# The third door. Tapping an empty table asked for a Customer before anything else, so a
# check could start with no waiter and no covers — the two things the floor exists to record.
P = ("apps/restaurant_management/restaurant_management/public/restaurant/js/"
     "restaurant-object-class.js")

src = open(P).read()

# An earlier bake put this inside _open(), which upstream only reaches after the customer
# dialog it was meant to replace. Lift it out before inserting it at the real door.
STALE = """        // rm_tile_seats: an empty table is seated through the door — PIN, waiter,
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
"""
if STALE in src:
    src = src.replace(STALE, "", 1)
    open(P, "w").write(src)
    print("tile seats: lifted the earlier block out of _open()")

if "rm_tile_seats" in src:
    print("tile seats: already at the door")
    raise SystemExit

# the customer dialog sits between these two branches; seat before it is ever reached,
# and after the navigate_table branch so the pad still opens once the party is seated
OLD = """          if (RM.navigate_table) {
            RM.navigate_table = null;
            _open();
            return;
          }

          if (this.hasCustomer()) {"""

NEW = """          if (RM.navigate_table) {
            RM.navigate_table = null;
            _open();
            return;
          }

          // rm_tile_seats: an empty table is seated through the door first — waiter PIN,
          // guest, covers — instead of opening a check against a bare customer name.
          if (window.RM_host_stand && RM_host_stand.open_for && !this.__rm_seating
              && !RM.transfer_order && !RM.editing) {
            const occ = window.RM_seats && RM_seats.seats && RM_seats.seats(this.data.name);
            const parties = occ && occ.parties ? occ.parties.length : 0;
            if (!parties && !(this.data.orders_count > 0)) {
              this.__rm_seating = true;
              setTimeout(() => { this.__rm_seating = false; }, 30000);
              RM_host_stand.open_for(this.data.name, null, () => { this.__rm_seating = false; });
              return;
            }
          }

          if (this.hasCustomer()) {"""

if src.count(OLD) != 1:
    raise SystemExit("tile seats: open() anchor found %d times" % src.count(OLD))

open(P, "w").write(src.replace(OLD, NEW, 1))
print("tile seats: an empty table seats a party before any check exists")
