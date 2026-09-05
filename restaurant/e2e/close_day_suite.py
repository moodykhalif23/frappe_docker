"""Closing the day leaves an unpaid check standing, and says so by name: table,
guest and amount. Test sites only — it closes and reopens the day."""
import json
import frappe
from restaurant_management import house

PASSED = []


def ok(name, cond, detail=""):
	PASSED.append(bool(cond))
	print("%s  %s%s" % ("PASS" if cond else "FAIL", name, ("   [%s]" % detail) if detail else ""))


def run():
	frappe.set_user("geff@etham.co.ke")
	if not house.house_shift():
		house.open_day(balances=json.dumps({"Cash": 5000}))
		frappe.db.commit()
	table = [t["name"] for t in house.free_tables() if not str(t.get("description", "")).startswith("Delivery")][0]
	seat = house.seat_walkin("Unpaid Guest", 2, table, waiter="Amina Test", pin="1111")
	doc = frappe.get_doc("Table Order", seat["order"])
	menu = frappe.db.get_value("POS Profile", {"disabled": 0}, "restaurant_menu")
	item = frappe.get_all("Restaurant Menu Item", filters={"parent": menu, "status": 1}, fields=["item"], limit=1)[0].item
	rate = float(frappe.db.get_value("Item Price", {"item_code": item, "selling": 1}, "price_list_rate") or 100)
	doc.push_item(dict(name=None, entry_name=None, identifier=frappe.generate_hash(length=10), item_code=item,
					   item_name=frappe.db.get_value("Item", item, "item_name"), qty=1, rate=rate, price_list_rate=rate,
					   discount_percentage=0, discount_amount=0, stock_uom=frappe.db.get_value("Item", item, "stock_uom"),
					   item_invoice=None, item_invoice_name=None, ordered_time=None, has_serial_no=0, serial_no=None,
					   has_batch_no=0, batch_no=None, status="Pending", notes=""))
	frappe.db.commit()
	res = house.close_day(force=1)
	frappe.db.commit()
	left = res.get("open_checks_detail") or []
	mine = [c for c in left if c["order"] == seat["order"]]
	ok("closing names the unpaid check left standing", len(mine) == 1, json.dumps(left)[:200])
	ok("with its table, guest and amount", mine and mine[0]["table"] == frappe.db.get_value("Restaurant Object", table, "description")
	   and mine[0]["customer"] == seat["customer"] and abs(mine[0]["amount"] - rate) < 0.01, json.dumps(mine)[:160])
	ok("the check itself is untouched — nobody's money vanished",
	   frappe.db.get_value("Table Order", seat["order"], "status") not in ("Cancelled", "Invoiced"))
	house.release_table(table)
	house.open_day(balances=json.dumps({"Cash": 5000}))
	frappe.db.commit()
	print("%d/%d passed" % (sum(PASSED), len(PASSED)))
	if not all(PASSED):
		raise AssertionError("close day suite failed")
