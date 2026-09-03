# After "Update Table" saves, the tile still showed the old name: the room's
# objects are keyed by docname and a rename is a new key. Redraw the room.
P = "apps/restaurant_management/restaurant_management/public/restaurant/js/restaurant-object-class.js"

src = open(P).read()
if "rm_rename_refresh" in src:
    print("rename refresh: already applied")
    raise SystemExit

OLD = '''          form_name: this.data.type === "Table" ? "restaurant-table" : "restaurant-production-center",
          callback: (self) => {
            self.hide();
          },'''
NEW = '''          form_name: this.data.type === "Table" ? "restaurant-table" : "restaurant-production-center",
          callback: (self) => {
            self.hide();
            // rm_rename_refresh: a changed description is a rename — redraw the room
            if (self.doc && self.doc.description && self.doc.description !== this.data.name) {
              this.edit_form = null;
              setTimeout(() => RM.current_room && RM.current_room.select(), 400);
            }
          },'''
if src.count(OLD) != 1:
    raise SystemExit("rename refresh: expected exactly one Update Table callback, found %d" % src.count(OLD))
open(P, "w").write(src.replace(OLD, NEW, 1))
print("rename refresh: the room redraws after a rename")
