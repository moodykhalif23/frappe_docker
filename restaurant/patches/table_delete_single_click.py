# The trash on a table was bound with DOUBLE_CLICK, so a single tap did nothing
P = "apps/restaurant_management/restaurant_management/public/restaurant/js/restaurant-object-class.js"

src = open(P).read()
# The later explains-patch renames this marker, so recognise either: the patch
if "rm_confirm_delete" in src or "rm_delete_explains" in src:
    print("table delete gesture: already applied")
    raise SystemExit

OLD = """      content: '<span class="fa fa-trash"></span>'
    }).on("click", () => {
      this.delete();
    }, DOUBLE_CLICK);"""

NEW = """      content: '<span class="fa fa-trash"></span>'
    }).on("click", () => {
      const label = this.data.description || this.data.name;   // rm_confirm_delete
      frappe.confirm(__("Delete {0}?", [label]), () => this.delete());
    });"""

if OLD not in src:
    raise SystemExit("table delete gesture: anchor not found")

open(P, "w").write(src.replace(OLD, NEW, 1))
print("table delete gesture: single click with confirm")
