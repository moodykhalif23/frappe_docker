"""A customer name attached to a table with no check and no party is a leftover:
the next occupancy fetch clears it. Test sites only — it writes to a table."""
import frappe
from restaurant_management import house

PASSED = []


def ok(name, cond, detail=""):
	PASSED.append(bool(cond))
	print("%s  %s%s" % ("PASS" if cond else "FAIL", name, ("   [%s]" % detail) if detail else ""))


def run():
	frappe.set_user("Administrator")
	free = [t["name"] for t in house.free_tables() if not str(t.get("description", "")).startswith("Delivery")
			and not frappe.db.count("Table Order", {"table": t["name"], "status": ["not in", ["Cancelled", "Invoiced"]]})]
	table = free[0]
	frappe.db.set_value("Restaurant Object", table, "customer", "Ghost Guest", update_modified=False)
	frappe.db.commit()
	ok("a ghost name sits on a free table", frappe.db.get_value("Restaurant Object", table, "customer") == "Ghost Guest", table)
	house.table_occupancy()
	frappe.db.commit()
	ok("one occupancy fetch clears it", not frappe.db.get_value("Restaurant Object", table, "customer"))
	# a table with a real party keeps its guest
	seat = house.seat_walkin("Real Guest", 1, free[1], waiter="Amina Test", pin="1111")
	frappe.db.commit()
	house.table_occupancy()
	frappe.db.commit()
	ok("a seated table keeps its guest", frappe.db.get_value("Restaurant Object", free[1], "customer") == seat["customer"])
	house.release_party(seat["booking"]) if hasattr(house, "release_party") else None
	frappe.db.commit()
	print("%d/%d passed" % (sum(PASSED), len(PASSED)))
	if not all(PASSED):
		raise AssertionError("stale marker suite failed")
