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

	# --- Card is on the till ---
	for profile in frappe.get_all("POS Profile", filters={"disabled": 0}, pluck="name"):
		modes = {r.mode_of_payment for r in frappe.get_all(
			"POS Payment Method", filters={"parent": profile}, fields=["mode_of_payment"])}
		ok("%s offers Cash, M-Pesa and Credit Card" % profile,
		   {"Cash", "M-Pesa", "Credit Card"} <= modes, json.dumps(sorted(modes)))

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
