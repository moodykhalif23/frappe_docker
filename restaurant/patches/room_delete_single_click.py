# The room's Delete button was bound with DOUBLE_CLICK too: a single tap did
# nothing and said nothing, which reads as "deleting rooms is broken".
P = "apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js"

src = open(P).read()
if "rm_confirm_room_delete" in src:
    print("room delete gesture: already applied")
    raise SystemExit

OLD = """    }).on("click", () => {
      if (this.current_room != null) this.current_room.delete();
    }, DOUBLE_CLICK);"""

NEW = """    }).on("click", () => {
      if (this.current_room == null) return;
      const label = this.current_room.data.description || this.current_room.data.name;   // rm_confirm_room_delete
      frappe.confirm(__("Delete room {0}? Its tables must be moved or deleted first.", [label]),
        () => this.current_room.delete());
    });"""

if OLD not in src:
    raise SystemExit("room delete gesture: anchor not found")

open(P, "w").write(src.replace(OLD, NEW, 1))
print("room delete gesture: single click with confirm")
