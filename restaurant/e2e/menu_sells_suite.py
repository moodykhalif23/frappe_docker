"""A dish joins the menu with Maintain Stock left on (the Item form's default):
saving the menu switches it to non-stock, so the till can sell it. An item with
real stock history is left alone. Test sites only."""
import frappe

PASSED = []


def ok(name, cond, detail=""):
	PASSED.append(bool(cond))
	print("%s  %s%s" % ("PASS" if cond else "FAIL", name, ("   [%s]" % detail) if detail else ""))


def run():
	frappe.set_user("Administrator")
	menu = frappe.db.get_value("POS Profile", {"disabled": 0}, "restaurant_menu")
	group = frappe.db.get_value("Item", {"is_sales_item": 1, "is_stock_item": 0}, "item_group") or "Products"
	code = "ZZ Stocked Dish %s" % frappe.generate_hash(length=4).upper()
	frappe.get_doc({"doctype": "Item", "item_code": code, "item_name": code, "item_group": group, "stock_uom": "Nos",
					"is_stock_item": 1, "is_sales_item": 1, "item_type": "Veg"}).insert(ignore_permissions=True)
	ok("a dish made on the Item form starts as a stocked item", frappe.db.get_value("Item", code, "is_stock_item") == 1)
	m = frappe.get_doc("Restaurant Menu", menu)
	m.append("menu_items", {"item": code, "rate": 100, "status": 1})
	m.save(ignore_permissions=True)
	frappe.db.commit()
	ok("joining the menu switches it to non-stock", frappe.db.get_value("Item", code, "is_stock_item") == 0)
	# an ingredient with stock history is not touched
	ingredient = frappe.db.get_value("Stock Ledger Entry", {"is_cancelled": 0}, "item_code")
	if ingredient:
		before = frappe.db.get_value("Item", ingredient, "is_stock_item")
		from restaurant_management import house
		house.menu_sells_without_stock(menu)
		ok("an item with stock history keeps Maintain Stock", frappe.db.get_value("Item", ingredient, "is_stock_item") == before)
	# tidy: take the test dish off the menu again
	m = frappe.get_doc("Restaurant Menu", menu)
	m.menu_items = [r for r in m.menu_items if r.item != code]
	m.save(ignore_permissions=True)
	frappe.db.commit()
	print("%d/%d passed" % (sum(PASSED), len(PASSED)))
	if not all(PASSED):
		raise AssertionError("menu sells suite failed")
