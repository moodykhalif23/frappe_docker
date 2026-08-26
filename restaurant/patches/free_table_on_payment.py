# Paying the check left the booking Open, so the table only became free when its
# two-hour window lapsed. Closing it here stamps the turn the report reads.
P = "apps/restaurant_management/restaurant_management/restaurant_management/doctype/table_order/table_order.py"

src = open(P).read()
ANCHOR = """        frappe.db.set_value("Table Order", self.name, "docstatus", 1)
"""
ADD = """        frappe.db.set_value("Table Order", self.name, "docstatus", 1)

        try:
            from restaurant_management.house import free_table
            free_table(self.table, booking=self.get("booking"))
        except Exception:
            # A paid invoice must never roll back because the floor bookkeeping failed.
            frappe.log_error(title="free_table after payment")
"""

# An earlier bake freed every party on the table; on a shared table that evicted
# the strangers sitting next to the one who paid.
OLD_CALL = "free_table(self.table)"
NEW_CALL = 'free_table(self.table, booking=self.get("booking"))'

if OLD_CALL in src:
    open(P, "w").write(src.replace(OLD_CALL, NEW_CALL, 1))
    print("free_table: narrowed to the paying party")
    raise SystemExit

if NEW_CALL in src:
    print("free_table: already hooked")
    raise SystemExit
if ANCHOR not in src:
    raise SystemExit("free_table: anchor not found in table_order.py")

open(P, "w").write(src.replace(ANCHOR, ADD, 1))
print("free_table: paying party released on payment")
