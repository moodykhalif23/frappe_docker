# Deleting a room never worked. The room's delete() called `_delete` through
# restaurant_management.api.call without `args`, and that dispatcher only
# *invokes* a method when args are sent — so it fetched the bound method and
# returned, nothing was deleted, nothing was said (fix_table_delete.py fixed the
# same call for tables only). Called properly, frappe would still refuse any
# room with a table in it, in its raw link-error wording.
#
# delete() now asks house.room_blockers what the room holds, names everything
# that will go with it, and deletes the lot through house.delete_room — or
# says plainly what keeps it. The floor then lands on another room.
#
# Replaces room_delete_single_click.py. Each edit replaces a whole span, so it
# upgrades upstream source, that patch's confirm, and any earlier build of this.
import re
import sys

sys.path.insert(0, "/tmp")
from _patchlib import tag_for  # noqa: E402

PAGE = "apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js"
ROOM = "apps/restaurant_management/restaurant_management/public/restaurant/js/restaurant-room-class.js"

BUTTON = """.on("click", () => {
      // @TAG@: the room's delete() asks first, naming what goes with it
      if (this.current_room != null) this.current_room.delete();
    });
"""

METHOD = """
  delete() {
    // @TAG@: name what goes with the room, or say plainly what keeps it
    if (RM.busy_message()) return;
    const room = this.data.name;
    frappe.call({
      method: "restaurant_management.house.room_blockers",
      args: { room },
      callback: (r) => {
        const b = r.message;
        if (!b) return;
        if (b.reasons.length) {
          const items = b.reasons.map((x) => `<li>${frappe.utils.escape_html(x)}</li>`).join("");
          frappe.msgprint({
            title: __("{0} can't be deleted", [b.label]),
            indicator: "orange",
            message: `<ul>${items}</ul><p>${__("A check or a seating is part of the books, so the room and table it belongs to stay. Rename the room instead, or delete the tables in it that have nothing on record.")}</p>`
          });
          return;
        }
        const names = b.contents.map((o) => o.label);
        const prompt = names.length
          ? __("Delete room {0} and everything in it ({1})?", [b.label, names.join(", ")])
          : __("Delete room {0}?", [b.label]);
        frappe.confirm(prompt, () => {
          RM.working("Deleting Room");
          frappe.call({
            method: "restaurant_management.house.delete_room",
            args: { room },
            callback: () => {
              if (RM.current_room && RM.current_room.data.name === room) RM.delete_current_room();
              RM.make_rooms();
            },
            always: () => RM.ready()
          });
        });
      }
    });
  }
"""

button_tag = tag_for("room_delete_button", BUTTON)
method_tag = tag_for("room_delete", METHOD)

# --- the Delete button: keep the component, replace its click binding ----------
page = open(PAGE).read()
if button_tag in page:
    print("room delete button: already current")
else:
    pat = re.compile(
        r'(    this\.#components\.delete_room = frappe\.jshtml\(\{.*?\n    \}\))'
        r'\.on\("click", \(\) => \{.*?\n    \}(?:, DOUBLE_CLICK)?\);\n',
        re.S)
    page, n = pat.subn(lambda m: m.group(1) + BUTTON.replace("@TAG@", button_tag), page, count=1)
    if n != 1:
        raise SystemExit("room delete button: anchor not found")
    open(PAGE, "w").write(page)
    print("room delete button: single click, delete() asks")

# --- RestaurantRoom.delete(): the whole method ---------------------------------
room = open(ROOM).read()
if method_tag in room:
    print("room delete: already current")
else:
    pat = re.compile(r"\n  delete\(\) \{\n.*?\n  \}\n", re.S)
    room, n = pat.subn(lambda m: METHOD.replace("@TAG@", method_tag), room, count=1)
    if n != 1:
        raise SystemExit("room delete: delete() anchor not found")
    open(ROOM, "w").write(room)
    print("room delete: names what goes, deletes through house.delete_room")

# post-conditions: the new code is in, and nothing of the old paths survives
page, room = open(PAGE).read(), open(ROOM).read()
assert button_tag in page and method_tag in room, "room delete: marker missing after apply"
assert 'method: "_delete"' not in room, "room delete: upstream _delete call survived"
assert "Its tables must be moved or deleted first" not in page, "room delete: old confirm survived"
print("room delete: %s / %s" % (button_tag, method_tag))
