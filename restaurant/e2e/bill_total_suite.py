"""A printed bill adds up. Test sites only: it seats a party and rings dishes.

6 Nov 2026, OR-2026-03071: the bill listed lines adding to 620 under "Total
Sh 470.00". A +/- on a dish already on the check committed the line, then took
about a second to recompute the check's total; the bill was read in between.

  1. the line and the total are committed together: a second database
     connection looking in at the moment the total is about to be recomputed
     sees the check as it was, never the new line under the old total.
  2. the bill's Total is the sum of the lines it prints even when the stored
     total is stale.
  3. on a check whose stored total is right, the Total reads exactly as before.
  4. splitting a check used to commit a whole line's removal before adding it
     to the new check; a split that fails halfway now leaves the check whole,
  5. and one that succeeds leaves both checks' totals true, with nothing lost.
"""
import json
import re

import frappe
from frappe.database import get_db
from restaurant_management import house
from restaurant_management.restaurant_management.doctype.table_order.table_order import TableOrder

PASSED = []
WAITER, PIN = "Bill Test Waiter", "4821"
BILL = "Etham Order Bill"


def ok(name, cond, detail=""):
	PASSED.append(bool(cond))
	print("%s  %s%s" % ("PASS" if cond else "FAIL", name, ("   [%s]" % detail) if detail else ""))


def _waiter():
	name = frappe.db.get_value("Restaurant Waiter", {"waiter_name": WAITER})
	doc = frappe.get_doc("Restaurant Waiter", name) if name else frappe.get_doc(
		{"doctype": "Restaurant Waiter", "waiter_name": WAITER, "colour": "#2563eb"})
	doc.pin, doc.active = PIN, 1
	doc.save(ignore_permissions=True)
	return doc.name


def _line(item, qty):
	rate = float(frappe.db.get_value("Item Price", {"item_code": item, "selling": 1}, "price_list_rate") or 100)
	return dict(name=None, entry_name=None, identifier=frappe.generate_hash(length=10), item_code=item,
				item_name=frappe.db.get_value("Item", item, "item_name"), qty=qty, rate=rate, price_list_rate=rate,
				discount_percentage=0, discount_amount=0, stock_uom=frappe.db.get_value("Item", item, "stock_uom"),
				item_invoice=None, item_invoice_name=None, ordered_time=None, has_serial_no=0, serial_no=None,
				has_batch_no=0, batch_no=None, status="Pending", notes="")


def _bill(name):
	"""The bill as the till prints it: (lines [(item, qty, amount)], printed total)."""
	html = frappe.get_print("Table Order", name, BILL)
	lines = [(n.strip(), float(q), float(a)) for n, q, a in re.findall(
		r'<td class="it">([^<]*)(?:<span[^>]*>[^<]*</span>|\s)*</td>\s*<td class="qt">([\d.]+)</td>\s*'
		r'<td class="am">([\d.,]+)</td>', html)]
	total = re.search(r'<tr class="tot"><td class="tl">[^<]*</td><td class="am">([^<]*)</td>', html)
	return lines, (total.group(1).strip() if total else None)


def _money(s):
	return float(re.sub(r"[^\d.\-]", "", s or "") or "nan")


def run():
	frappe.set_user("Administrator")
	house.ensure_custom_fields()  # puts the template from the image onto the bill format
	if not house.house_shift():
		house.open_day(balances=json.dumps({"Cash": 5000}))
	waiter = _waiter()
	frappe.db.commit()

	table = [t["name"] for t in house.free_tables() if not str(t.get("description", "")).startswith("Delivery")][0]
	seat = house.seat_walkin("Bill Test Party", 2, table, waiter=waiter, pin=PIN)
	doc = frappe.get_doc("Table Order", seat["order"])
	menu = frappe.db.get_value("POS Profile", {"disabled": 0}, "restaurant_menu")
	items = [r.item for r in frappe.get_all("Restaurant Menu Item", filters={"parent": menu, "status": 1},
											fields=["item"], limit=2)]
	for it in items:
		doc.push_item(_line(it, 1))
	frappe.db.commit()
	doc.reload()
	first = doc.items_list()[0]
	before = float(doc.amount)

	# 1 --------------------------------------------------------------------
	# Look in from a second connection at the moment aggregate() is about to
	# recompute the total: whatever is committed then is what a bill printed in
	# that instant would read.
	seen = {}
	original = TableOrder.aggregate

	def look_in(self):
		c = frappe.conf
		other = get_db(socket=c.db_socket, host=c.db_host, port=c.db_port, user=c.db_user or c.db_name,
					   password=c.db_password, cur_db_name=c.db_name)
		try:
			seen["outside"] = other.sql(
				"select o.amount, (select sum(i.amount) from `tabOrder Entry Item` i where i.parent=o.name)"
				" from `tabTable Order` o where o.name=%s", self.name)[0]
		finally:
			other.close()
		return original(self)

	first["qty"] = 2
	TableOrder.aggregate = look_in
	try:
		doc.push_item(first)
	finally:
		TableOrder.aggregate = original
	frappe.db.commit()
	amount, lines = seen["outside"]
	ok("mid-update, another connection never sees a line the total does not include",
	   abs(float(amount) - float(lines)) < 0.005, "stored total %s, lines %s" % (amount, lines))
	doc.reload()
	ok("after the +, the stored total is the lines' sum and one dish more",
	   abs(doc.amount - sum(i.amount for i in doc.entry_items)) < 0.005 and doc.amount > before,
	   "%s -> %s" % (before, doc.amount))

	# 3 --------------------------------------------------------------------
	_, printed = _bill(doc.name)
	ok("on a consistent check the Total prints exactly as before",
	   printed == doc.get_formatted("amount"), "%r vs %r" % (printed, doc.get_formatted("amount")))

	# 2 --------------------------------------------------------------------
	# Recreate the 6 Nov state by hand: a line bumped, the stored total not.
	row = doc.entry_items[0]
	frappe.db.set_value("Order Entry Item", row.name, {"qty": row.qty + 1, "amount": row.amount + row.rate},
						update_modified=False)
	frappe.db.commit()
	lines, printed = _bill(doc.name)
	ok("a stale stored total no longer reaches the bill: Total = sum of the printed lines",
	   lines and abs(_money(printed) - sum(a for _, _, a in lines)) < 0.005,
	   "lines %s, Total %r, stored %s" % (lines, printed, frappe.db.get_value("Table Order", doc.name, "amount")))

	frappe.db.set_value("Order Entry Item", row.name, {"qty": row.qty, "amount": row.amount}, update_modified=False)
	frappe.db.commit()

	# 4 --------------------------------------------------------------------
	# Divide moves a whole line by deleting it here first and adding it to the
	# new check after. Make the add fail: the check must come back whole.
	doc.reload()
	whole = sum(i.amount for i in doc.entry_items)
	moves = {i.identifier: {"qty": i.qty, "identifier": "entry_" + frappe.generate_hash(length=10)}
			 for i in doc.entry_items}
	original_update = TableOrder.update_item

	def fail_on_new_check(self, entry, *a, **kw):
		if self.name != doc.name:
			raise frappe.ValidationError("suite: the new check refuses its first line")
		return original_update(self, entry, *a, **kw)

	TableOrder.update_item = fail_on_new_check
	try:
		doc.divide(moves, "bill_total_suite")
	except frappe.ValidationError:
		pass
	finally:
		TableOrder.update_item = original_update
	frappe.db.rollback()
	kept = frappe.db.sql("select count(*), sum(amount) from `tabOrder Entry Item` where parent=%s", doc.name)[0]
	ok("a split that fails halfway leaves the check whole",
	   kept[0] == len(moves) and abs(float(kept[1] or 0) - whole) < 0.005,
	   "%s lines, %s, was %s lines, %s" % (kept[0], kept[1], len(moves), whole))

	# 5 --------------------------------------------------------------------
	doc.reload()
	a, b = doc.entry_items[0], doc.entry_items[1]
	since = frappe.utils.now()
	doc.divide({a.identifier: {"qty": 1, "identifier": "entry_" + frappe.generate_hash(length=10)},
				b.identifier: {"qty": b.qty, "identifier": "entry_" + frappe.generate_hash(length=10)}},
			   "bill_total_suite")
	frappe.db.commit()
	new = frappe.db.get_value("Table Order", {"table": doc.table, "name": ["!=", doc.name],
											  "creation": [">=", since]}, "name", order_by="creation desc")
	sums = {n: (float(frappe.db.get_value("Table Order", n, "amount")),
				float(frappe.db.sql("select ifnull(sum(amount),0) from `tabOrder Entry Item` where parent=%s", n)[0][0]))
			for n in (doc.name, new) if n}
	ok("a split keeps both checks' totals true and loses nothing",
	   new and all(abs(s - l) < 0.005 for s, l in sums.values())
	   and abs(sum(s for s, _ in sums.values()) - whole) < 0.005,
	   "%s, was %s" % (sums, whole))

	house.release_table(table)
	frappe.db.commit()
	print("%d/%d passed" % (sum(PASSED), len(PASSED)))
	if not all(PASSED):
		raise AssertionError("bill total suite failed")
