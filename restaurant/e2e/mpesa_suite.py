"""M-Pesa on the server: an M-Pesa row must carry a well-formed, unused code;
cash needs none; the code lands on the payment row; the report finds it.
Runs in the bench console of a test site — it bills real invoices."""
import json
import frappe
from frappe import _
from restaurant_management import house

PASSED = []


def ok(name, cond, detail=""):
	PASSED.append(bool(cond))
	print("%s  %s%s" % ("PASS" if cond else "FAIL", name, ("   [%s]" % detail) if detail else ""))


def _menu_item():
	# a dish on the profile's menu, priced on its selling price list
	menu = frappe.db.get_value("POS Profile", {"disabled": 0}, "restaurant_menu")
	for row in frappe.get_all("Restaurant Menu Item", filters={"parent": menu, "status": 1}, fields=["item"], limit=20):
		rate = frappe.db.get_value("Item Price", {"item_code": row.item, "selling": 1}, "price_list_rate")
		if rate:
			return row.item, float(rate)
	frappe.throw("no priced dish on the menu")


def _check(guest, table):
	seat = house.seat_walkin(guest, 1, table, waiter="Amina Test", pin="1111")
	doc = frappe.get_doc("Table Order", seat["order"])
	item, rate = _menu_item()
	# the same shape the pad posts
	doc.push_item(dict(name=None, entry_name=None, identifier=frappe.generate_hash(length=10), item_code=item,
					   item_name=frappe.db.get_value("Item", item, "item_name"), qty=1, rate=rate,
					   price_list_rate=rate, discount_percentage=0, discount_amount=0,
					   stock_uom=frappe.db.get_value("Item", item, "stock_uom"), item_invoice=None,
					   item_invoice_name=None, ordered_time=None, has_serial_no=0, serial_no=None,
					   has_batch_no=0, batch_no=None, status="Pending", notes=""))
	frappe.db.commit()  # a refused payment rolls back; the check must survive it
	doc = frappe.get_doc("Table Order", seat["order"])
	return doc, float(doc.amount or rate)


def _throws(fn, needle):
	try:
		fn()
	except Exception as e:
		frappe.db.rollback()
		frappe.clear_messages()
		return needle.lower() in str(e).lower(), str(e)[:120]
	return False, "no error"


def _free_table():
	for t in house.free_tables():
		if t.get("type", "Table") == "Table" and not str(t.get("description", "")).startswith("Delivery"):
			return t["name"]
	frappe.throw("no free table on the test floor")


def run():
	frappe.set_user("cashier@etham.co.ke")
	tag = frappe.generate_hash(length=4).upper()
	code = "Q" + frappe.generate_hash(length=9).upper()

	doc, total = _check("Mpesa Srv %s" % tag, _free_table())
	hit, msg = _throws(lambda: doc.make_invoice({"M-Pesa": total}), "confirmation code")
	ok("an M-Pesa row without a code is refused", hit, msg)
	doc = frappe.get_doc("Table Order", doc.name)
	hit, msg = _throws(lambda: doc.make_invoice({"M-Pesa": total}, references={"M-Pesa": "abc12"}), "confirmation code")
	ok("a short code is refused", hit, msg)
	doc = frappe.get_doc("Table Order", doc.name)
	doc.make_invoice({"M-Pesa": total}, references={"M-Pesa": code.lower()})
	frappe.db.commit()
	inv = frappe.get_doc("POS Invoice", frappe.db.get_value("Table Order", doc.name, "link_invoice"))
	row = [r for r in inv.payments if r.amount][0]
	ok("the code lands upper-cased on the payment row", row.mode_of_payment == "M-Pesa" and row.reference_no == code,
	   "%s %s" % (row.mode_of_payment, row.reference_no))
	ok("the invoice is submitted and paid", inv.docstatus == 1 and float(inv.paid_amount) >= total, "%s paid %s" % (inv.name, inv.paid_amount))

	doc2, total2 = _check("Mpesa Dup %s" % tag, _free_table())
	hit, msg = _throws(lambda: doc2.make_invoice({"M-Pesa": total2}, references={"M-Pesa": code}), "already paid")
	ok("the same code cannot pay a second bill", hit, msg)
	doc2 = frappe.get_doc("Table Order", doc2.name)
	doc2.make_invoice({"Cash": total2})
	frappe.db.commit()
	inv2 = frappe.get_doc("POS Invoice", frappe.db.get_value("Table Order", doc2.name, "link_invoice"))
	ok("cash needs no code", inv2.docstatus == 1 and not [r for r in inv2.payments if r.amount][0].reference_no)

	# through frappe's own runner, the way the desk calls it — the module path is derived from the name
	from frappe.desk.query_report import run as run_report
	today = frappe.utils.today()
	rows = [frappe._dict(r) for r in run_report("M-Pesa Payments", filters={"from_date": today, "to_date": today, "code": code})["result"] if isinstance(r, dict)]
	ok("the M-Pesa Payments report finds the code", len(rows) == 1 and rows[0].invoice == inv.name and rows[0].waiter == "Amina Test",
	   json.dumps([dict(r) for r in rows], default=str)[:160])
	allrows = [frappe._dict(r) for r in run_report("M-Pesa Payments", filters={"from_date": today, "to_date": today})["result"] if isinstance(r, dict)]
	ok("the report lists only M-Pesa rows", allrows and all("pesa" in r.mode.lower() for r in allrows), "%d rows" % len(allrows))

	# one bill, two M-Pesa transactions: two rows, two codes, the amounts adding up
	doc3, total3 = _check("Mpesa Split %s" % tag, _free_table())
	c1, c2 = "Q" + frappe.generate_hash(length=9).upper(), "Q" + frappe.generate_hash(length=9).upper()
	hit, msg = _throws(lambda: doc3.make_invoice({"M-Pesa": total3}, references={"M-Pesa": [
		{"amount": total3 - 50, "code": c1}, {"amount": 40, "code": c2}]}), "add up")
	ok("transactions that do not add up to the bill are refused", hit, msg)
	doc3 = frappe.get_doc("Table Order", doc3.name)
	hit, msg = _throws(lambda: doc3.make_invoice({"M-Pesa": total3}, references={"M-Pesa": [
		{"amount": total3 - 50, "code": c1}, {"amount": 50, "code": c1}]}), "twice")
	ok("the same code twice on one bill is refused", hit, msg)
	doc3 = frappe.get_doc("Table Order", doc3.name)
	doc3.make_invoice({"M-Pesa": total3}, references={"M-Pesa": [{"amount": total3 - 50, "code": c1}, {"amount": 50, "code": c2.lower()}]})
	frappe.db.commit()
	inv3 = frappe.get_doc("POS Invoice", frappe.db.get_value("Table Order", doc3.name, "link_invoice"))
	rows3 = [(r.mode_of_payment, float(r.amount), r.reference_no) for r in inv3.payments if r.amount]
	ok("two transactions land as two M-Pesa rows with their own codes",
	   rows3 == [("M-Pesa", float(total3 - 50), c1), ("M-Pesa", 50.0, c2)] and inv3.docstatus == 1, str(rows3))
	split_rows = [frappe._dict(r) for r in run_report("M-Pesa Payments", filters={"from_date": today, "to_date": today})["result"] if isinstance(r, dict)]
	ok("the report lists each transaction on its own line", sorted(r.code for r in split_rows if r.invoice == inv3.name) == sorted([c1, c2]))

	html = frappe.db.get_value("Print Format", "Etham Receipt", "html") or ""
	ok("the receipt is the compact one", "rm_receipt_v2" in html)
	out = frappe.get_print("POS Invoice", inv.name, "Etham Receipt")
	ok("the receipt shows the mode and its code", code in out and "M-Pesa" in out)
	ok("with item, qty and amount in their own columns",
	   'class="it"' in out and 'class="qt"' in out and 'class="am"' in out)

	frappe.db.commit()
	print("%d/%d passed" % (sum(PASSED), len(PASSED)))
	if not all(PASSED):
		raise AssertionError("mpesa suite failed")
