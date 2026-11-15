# Deleting a table: one tap, and either a plain answer or a confirm.
#
# The trash used to ask house.table_blockers, which counted only *invoiced*
# checks, then call `_delete` — and frappe refuses a delete over ANY linked row.
# A table with only a cancelled check or a released seating was called deletable
# and the trash threw frappe's raw link error; "Close them and delete it?" could
# never succeed, because releasing cancels checks and seatings but keeps them.
#
# The trash now shows table_blockers' reasons (frappe's own link check) and
# deletes through house.delete_table, which refuses the same way if anything
# changed in between. The tile goes on success even if the realtime event is lost.
#
# Replaces table_delete_single_click.py, table_delete_explains.py and the JS half
# of fix_table_delete.py. Each edit replaces a whole span, so it upgrades upstream
# source, those patches' output, and any earlier build of this.
import re
import sys

sys.path.insert(0, "/tmp")
from _patchlib import tag_for  # noqa: E402

P = "apps/restaurant_management/restaurant_management/public/restaurant/js/restaurant-object-class.js"

TRASH = """.on("click", () => {
      // @TAG@: say plainly what keeps a table, or ask and delete it
      const table = this.data.name;
      frappe.call({
        method: "restaurant_management.house.table_blockers",
        args: { table },
        callback: (r) => {
          const b = r.message;
          if (!b) return;
          if (b.reasons.length) {
            const items = b.reasons.map((x) => `<li>${frappe.utils.escape_html(x)}</li>`).join("");
            const why = b.on_record
              ? `<p>${__("A check or a seating is part of the books, so the table it belongs to stays. Rename it if the floor has changed.")}</p>`
              : "";
            frappe.msgprint({
              title: __("{0} can't be deleted", [b.label]),
              indicator: "orange",
              message: `<ul>${items}</ul>${why}`
            });
            return;
          }
          frappe.confirm(__("Delete {0}?", [b.label]), () => this.delete());
        }
      });
    });
"""

METHOD = """
  delete() {
    // @TAG@: through house.delete_table, which refuses in plain words
    RM.working("Deleting Object");
    frappe.call({
      method: "restaurant_management.house.delete_table",
      args: { table: this.data.name },
      callback: () => {
        // the realtime Delete removes the tile too; do not depend on the socket
        if (this.room && this.room.has_child && this.room.has_child(this.data.name)) this.remove();
      },
      always: () => RM.ready(),
      freeze: true
    });
  }
"""

trash_tag = tag_for("table_delete_trash", TRASH)
method_tag = tag_for("table_delete", METHOD)

src = open(P).read()

if trash_tag in src:
    print("table delete trash: already current")
else:
    pat = re.compile(
        r"""(content: '<span class="fa fa-trash"></span>'\n    \}\))"""
        r"""\.on\("click", \(\) => \{.*?\n    \}(?:, DOUBLE_CLICK)?\);\n""",
        re.S)
    src, n = pat.subn(lambda m: m.group(1) + TRASH.replace("@TAG@", trash_tag), src, count=1)
    if n != 1:
        raise SystemExit("table delete trash: anchor not found")
    print("table delete trash: reasons from frappe's link check, or a confirm")

if method_tag in src:
    print("table delete: already current")
else:
    pat = re.compile(r"\n  delete\(\) \{\n.*?\n  \}\n", re.S)
    src, n = pat.subn(lambda m: METHOD.replace("@TAG@", method_tag), src, count=1)
    if n != 1:
        raise SystemExit("table delete: delete() anchor not found")
    print("table delete: deletes through house.delete_table")

open(P, "w").write(src)

# post-conditions: the new code is in, and nothing of the old paths survives
src = open(P).read()
assert trash_tag in src and method_tag in src, "table delete: marker missing after apply"
assert 'method: "_delete"' not in src, "table delete: upstream _delete call survived"
assert "house.release_table" not in src, "table delete: release-and-delete survived"
assert src.count('<span class="fa fa-trash"></span>') == 1, "table delete: expected one trash button"
print("table delete: %s / %s" % (trash_tag, method_tag))
