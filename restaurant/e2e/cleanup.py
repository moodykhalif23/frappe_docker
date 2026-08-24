# Remove what the suites leave behind. The browser suites write real records;
# the server suites clean up after themselves but a failed run can strand some.
#
#   exec(open(".../cleanup.py").read(), globals()); run()
#
# Paid invoices are reported, never cancelled — that is an accounting decision.

import frappe

PATTERNS = ["%Test Party%", "%Test Queue%", "%Test Booking%", "%Test Waiter%", "%Playwright%"]


def run():
	removed = {"order": 0, "booking": 0, "customer": 0, "waiter": 0, "employee": 0, "checkin": 0}
	kept = []

	customers = set()
	for pat in PATTERNS:
		for c in frappe.get_all("Customer", filters={"customer_name": ["like", pat]}, fields=["name"]):
			customers.add(c.name)

	for cust in customers:
		invoices = frappe.get_all("POS Invoice", filters={"customer": cust, "docstatus": 1}, fields=["name"])
		# An open Table Order keeps its table busy for good — deleting the booking
		# alone leaves the floor a table short after every test run.
		for o in frappe.get_all("Table Order", filters={"customer": cust},
		                        fields=["name", "table", "docstatus", "status"]):
			if o.status == "Invoiced":
				continue
			doc = frappe.get_doc("Table Order", o.name)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc("Table Order", o.name, force=1, ignore_permissions=True)
			if o.table and frappe.db.get_value("Restaurant Object", o.table, "customer") == cust:
				frappe.db.set_value("Restaurant Object", o.table, "customer", None)
			removed["order"] = removed.get("order", 0) + 1
		for b in frappe.get_all("Restaurant Booking", filters={"customer": cust}, fields=["name"]):
			frappe.db.set_value("Restaurant Booking", b.name, "table", None)
			frappe.delete_doc("Restaurant Booking", b.name, force=1, ignore_permissions=True)
			removed["booking"] += 1
		if invoices:
			kept.append("%s has %d submitted invoice(s): %s"
				% (cust, len(invoices), ", ".join(i.name for i in invoices)))
			continue
		try:
			frappe.delete_doc("Customer", cust, force=1, ignore_permissions=True)
			removed["customer"] += 1
		except Exception as e:
			kept.append("%s: %s" % (cust, str(e)[:80]))

	has_hrms = "hrms" in frappe.get_installed_apps()
	for pat in PATTERNS:
		for w in frappe.get_all("Restaurant Waiter", filters={"waiter_name": ["like", pat]}, fields=["name"]):
			frappe.delete_doc("Restaurant Waiter", w.name, force=1, ignore_permissions=True)
			removed["waiter"] += 1
		for e in frappe.get_all("Employee", filters={"employee_name": ["like", pat]}, fields=["name"]):
			if has_hrms:
				for ck in frappe.get_all("Employee Checkin", filters={"employee": e.name}, fields=["name"]):
					frappe.delete_doc("Employee Checkin", ck.name, force=1, ignore_permissions=True)
					removed["checkin"] += 1
			frappe.db.set_value("Employee", e.name, "status", "Left", update_modified=False)
			frappe.delete_doc("Employee", e.name, force=1, ignore_permissions=True)
			removed["employee"] += 1

	frappe.db.commit()
	print("removed:", removed)
	for line in kept:
		print("KEPT (cancel by hand if it was a test):", line)
	return "ok"
