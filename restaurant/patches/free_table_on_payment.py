# Paying the check left the booking Open, so the table only became free when its
# two-hour window lapsed. Closing it here frees the table at once and stamps the
# turn (seated -> left) that the table-turn report reads.
P = "apps/restaurant_management/restaurant_management/restaurant_management/doctype/table_order/table_order.py"

src = open(P).read()
ANCHOR = """        frappe.db.set_value("Table Order", self.name, "docstatus", 1)
"""
ADD = """        frappe.db.set_value("Table Order", self.name, "docstatus", 1)

        try:
            from restaurant_management.house import free_table
            free_table(self.table)
        except Exception:
            # A paid invoice must never roll back because the floor bookkeeping failed.
            frappe.log_error(title="free_table after payment")
"""

if "from restaurant_management.house import free_table" in src:
    print("free_table: already hooked")
    raise SystemExit
if ANCHOR not in src:
    raise SystemExit("free_table: anchor not found in table_order.py")

open(P, "w").write(src.replace(ANCHOR, ADD, 1))
print("free_table: table released on payment")
