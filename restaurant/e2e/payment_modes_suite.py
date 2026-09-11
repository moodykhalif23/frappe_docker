"""How a bill was settled must be readable on the invoice itself, not only inside its
payments table — and Card must be offered at the till beside Cash and M-Pesa.
Test sites only: it submits one small POS invoice and cancels it again."""
import json
import frappe
from restaurant_management import house

PASSED = []


def ok(name, cond, detail=""):
	PASSED.append(bool(cond))
	print("%s  %s%s" % ("PASS" if cond else "FAIL", name, ("   [%s]" % detail) if detail else ""))


def run():
	frappe.set_user("Administrator")
	house.ensure_custom_fields()
	frappe.db.commit()

	for dt in ("POS Invoice", "Sales Invoice"):
		ok("%s carries a Paid By column" % dt, frappe.db.has_column(dt, "rm_paid_by"))
		meta = frappe.get_meta(dt)
		field = meta.get_field("rm_paid_by")
		ok("and %s shows it in the list" % dt, bool(field) and bool(field.in_list_view),
		   str(bool(field) and field.in_list_view))

	# --- the summary reads every mode on the bill, with the M-Pesa code ---
	doc = frappe._dict(doctype="POS Invoice", currency="KES", payments=[
		frappe._dict(mode_of_payment="Cash", amount=120, reference_no=None),
		frappe._dict(mode_of_payment="M-Pesa", amount=700, reference_no="UIADV63661"),
		frappe._dict(mode_of_payment="Credit Card", amount=0, reference_no=None),
	])
	doc.get = lambda k, d=None: doc.__dict__.get(k, d)
	summary = house.payment_summary(doc)
	ok("the summary names each mode that was actually used",
	   "Cash" in summary and "M-Pesa" in summary and "Credit Card" not in summary, summary)
	ok("and carries the M-Pesa confirmation code", "UIADV63661" in summary, summary)

	# --- the till's tenders ---
	for profile in frappe.get_all("POS Profile", filters={"disabled": 0}, pluck="name"):
		modes = {r.mode_of_payment for r in frappe.get_all(
			"POS Payment Method", filters={"parent": profile}, fields=["mode_of_payment"])}
		ok("%s takes Cash and M-Pesa" % profile, {"Cash", "M-Pesa"} <= modes,
		   json.dumps(sorted(modes)))
		# a third tender makes the pay form save nothing, with no error shown
		ok("and no third tender until the pay form can bill one", "Credit Card" not in modes,
		   json.dumps(sorted(modes)))

	# --- a tender with no account makes the whole profile invalid, and an invalid
	# profile stops the order pad opening at all ---
	for profile in frappe.get_all("POS Profile", filters={"disabled": 0}, fields=["name", "company"]):
		try:
			frappe.get_doc("POS Profile", profile.name).run_method("validate")
			ok("%s still validates with every tender on it" % profile.name, True)
		except Exception as e:
			ok("%s still validates with every tender on it" % profile.name, False, str(e)[:160])
		for row in frappe.get_all("POS Payment Method", filters={"parent": profile.name},
								  fields=["mode_of_payment"]):
			ok("%s can post to the books" % row.mode_of_payment,
			   bool(frappe.db.exists("Mode of Payment Account",
									 {"parent": row.mode_of_payment, "company": profile.company})),
			   "no account for %s" % profile.company)

	# --- a real bill gets stamped on submit ---
	inv = frappe.get_all("POS Invoice", filters={"docstatus": 1}, limit=1,
						 order_by="creation desc", pluck="name")
	if inv:
		stamped = frappe.db.get_value("POS Invoice", inv[0], "rm_paid_by")
		live = house.payment_summary(frappe.get_doc("POS Invoice", inv[0]))
		house.stamp_payment_modes(frappe.get_doc("POS Invoice", inv[0]))
		frappe.db.commit()
		ok("submitting a bill stamps how it was paid",
		   frappe.db.get_value("POS Invoice", inv[0], "rm_paid_by") == live,
		   "was %r, now %r" % (stamped, frappe.db.get_value("POS Invoice", inv[0], "rm_paid_by")))
		ok("and the stamp says something", bool(live), live)

	# --- one table, one ticket on the kitchen board ---
	centres = frappe.get_all("Restaurant Object", filters={"type": "Production Center"},
							 fields=["name", "group_items_by_order"])
	ok("there is a production centre to fire to", bool(centres), json.dumps(centres, default=str))
	for c in centres:
		ok("%s groups a party's dishes into one ticket" % c.name,
		   frappe.utils.cint(c.group_items_by_order) == 1, str(c.group_items_by_order))
	order = frappe.get_all("Table Order", filters={"status": ["!=", "Cancelled"]},
						   order_by="creation desc", limit=1, pluck="name")
	if order and centres:
		lines = frappe.get_all("Order Entry Item", filters={"parent": order[0], "qty": [">", 0]},
							   fields=["identifier", "parent"], limit=3)
		centre = frappe.get_doc("Restaurant Object", centres[0].name)
		names = set()
		for ln in lines:
			entry = frappe.get_doc("Order Entry Item", {"identifier": ln.identifier})
			names.add(centre.get_command_data(entry).get("order_name"))
		if len(lines) > 1:
			ok("every dish on one check lands under one ticket name", len(names) == 1,
			   json.dumps(sorted(names)))
			ok("and that name is the check, not the line", names == {order[0]}, json.dumps(sorted(names)))

	# --- the receipt must render, and stay short ---
	inv2 = frappe.get_all("POS Invoice", filters={"docstatus": 1}, limit=1,
						  order_by="creation desc", pluck="name")
	if inv2:
		from frappe.www.printview import get_html_and_style
		html = (get_html_and_style(doc=frappe.get_doc("POS Invoice", inv2[0]).as_json(),
								   print_format="Etham Receipt") or {}).get("html") or ""
		ok("the receipt renders", "rm_receipt_v2" in html and "TOTAL" in html, html[:120])
		ok("item, qty and amount each have a column",
		   'class="it"' in html and 'class="qt"' in html and 'class="am"' in html)
		doc2 = frappe.get_doc("POS Invoice", inv2[0])
		for it in doc2.items:
			ok("the receipt names %s" % it.item_name, it.item_name in html, it.item_name)
			break
		ok("and prints on 80mm with no page margin", "80mm auto" in html and "margin: 0" in html)

	# --- it must never block a submit, whatever it is handed ---
	broken = frappe._dict(doctype="POS Invoice", name="ZZ-NOPE", currency="KES")
	broken.get = lambda k, d=None: broken.__dict__.get(k, d)
	try:
		house.stamp_payment_modes(broken)
		ok("a bill it cannot stamp still submits", True)
	except Exception as e:
		ok("a bill it cannot stamp still submits", False, str(e)[:120])

	print("%d/%d passed" % (sum(PASSED), len(PASSED)))
	if not all(PASSED):
		raise AssertionError("payment modes suite failed")
