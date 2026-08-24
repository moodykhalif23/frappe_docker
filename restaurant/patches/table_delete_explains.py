# Deleting a table threw frappe's raw link error — "Restaurant Object 5bdtibmn77
# is linked with Table Order OR-2026-00002" — which names neither the table nor
# anything the user can act on. Ask what is holding it first: an unpaid check can
# be closed on the spot, an invoiced one is a sale and the table has to stay.
P = "apps/restaurant_management/restaurant_management/public/restaurant/js/restaurant-object-class.js"

src = open(P).read()
if "rm_delete_explains" in src:
    print("table delete: already explains what blocks it")
    raise SystemExit

OLD = """      const label = this.data.description || this.data.name;   // rm_confirm_delete
      frappe.confirm(__("Delete {0}?", [label]), () => this.delete());"""

NEW = """      const label = this.data.description || this.data.name;   // rm_delete_explains
      const remove = () => this.delete();
      const table = this.data.name;
      frappe.call("restaurant_management.house.table_blockers", { table }).then((r) => {
        const b = r.message;
        if (!b) return frappe.confirm(__("Delete {0}?", [label]), remove);
        if (!b.deletable) {
          return frappe.msgprint({
            title: __("{0} has past sales", [b.label]),
            indicator: "orange",
            message: __("This table is on {0} invoiced order(s). Deleting it would break those records, so it stays. Rename it if the floor has changed.", [b.invoiced_orders])
          });
        }
        const checks = (b.open_orders || []).length;
        const seated = b.open_bookings || 0;
        if (!checks && !seated) return frappe.confirm(__("Delete {0}?", [label]), remove);
        frappe.confirm(
          __("{0} still holds {1} unpaid check(s) and {2} seated party. Close them and delete it?", [b.label, checks, seated]),
          () => frappe.call("restaurant_management.house.release_table", { table }).then(remove)
        );
      });"""

if OLD not in src:
    raise SystemExit("table delete: anchor not found (run table_delete_single_click.py first)")

open(P, "w").write(src.replace(OLD, NEW, 1))
print("table delete: explains what blocks it, and can clear an unpaid check")
