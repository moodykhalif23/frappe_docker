# Deleting a table relied on _delete being a @property, because the app's
# dispatcher (restaurant_management.api.call) only *calls* a method when args are
# sent — so a bare attribute access ran the delete. As a method it needs args.
# Making it a method silently broke the room's delete, which sent none; both
# floor deletes now go through house.delete_table / house.delete_room instead
# (table_delete.py, room_delete.py), so the old JS half of this patch is gone.
P = "apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_object/restaurant_object.py"

src = open(P).read()
OLD = """    @ property
    def _delete(self):
        self.delete()"""
NEW = """    def _delete(self):
        self.delete()"""
if OLD in src:
    open(P, "w").write(src.replace(OLD, NEW, 1))
    print("table delete: _delete is now a method")
elif NEW in src:
    print("table delete: _delete already a method")
else:
    raise SystemExit("table delete: python anchor not found")
