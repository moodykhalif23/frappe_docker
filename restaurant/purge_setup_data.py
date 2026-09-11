"""Erase the setup-day records so the books hold real trading only. Safe to re-run:
it finds nothing on a second run.

    ssh <host> "docker exec -i <backend> bash -lc 'cat > /tmp/purge.py'" \
        < restaurant/purge_setup_data.py
    ssh <host> "echo 'exec(open(\"/tmp/purge.py\").read(), globals()); run(dry=True)' \
        | docker exec -i <backend> bench --site <site> console"

Run it with dry=True first: it prints exactly what it would touch and changes nothing.
Then run() to do it.

frappe.ikobriq.com traded from 2026-09-06. Everything before that is setup: four bills
worth 2,550 against Walk-in Guest and a customer literally called "test", one of them
credited to the waiter "sharon" who exists only for that test.

Cancelling the POS Closing Entry does the whole reversal by itself — erpnext
unconsolidates the POS invoices, cancels the merge log and cancels the consolidated
Sales Invoice, which reverses the ledger. Only then is anything deleted, so the general
ledger is unwound properly rather than left with orphaned entries.

Numbers are NOT re-issued despite the delete: rm_series_never_rewinds already stops
revert_series_if_last handing an invoice or check number back to the next sale.
"""
import json

import frappe

CUTOFF = "2026-09-06"  # first day of real trading; everything before it is setup
WAITERS = ["sharon"]


def _targets(cutoff):
	pos = frappe.db.sql("""
		select name, posting_date, grand_total, waiter, customer, consolidated_invoice, docstatus
		from `tabPOS Invoice` where posting_date < %s order by name
	""", cutoff, as_dict=True)
	names = [p["name"] for p in pos]
	if not names:
		return pos, [], [], [], []
	sales = [p["consolidated_invoice"] for p in pos if p["consolidated_invoice"]]
	logs = frappe.db.sql_list("""
		select distinct parent from `tabPOS Invoice Reference`
		where pos_invoice in %(n)s and parenttype = 'POS Invoice Merge Log'
	""", {"n": tuple(names)})
	closings = frappe.db.sql_list("""
		select distinct parent from `tabPOS Invoice Reference`
		where pos_invoice in %(n)s and parenttype = 'POS Closing Entry'
	""", {"n": tuple(names)})
	checks = frappe.db.sql_list("""
		select name from `tabTable Order` where link_invoice in %(n)s or date(creation) < %(c)s
	""", {"n": tuple(names), "c": cutoff})
	return pos, sales, logs, closings, checks


def _guard_real_trading(closings, pos_names):
	"""Refuse if a closing entry from the setup days also banked a real sale."""
	bad = []
	for c in closings:
		others = frappe.db.sql_list("""
			select pos_invoice from `tabPOS Invoice Reference`
			where parent = %s and parenttype = 'POS Closing Entry' and pos_invoice not in %s
		""", (c, tuple(pos_names) or ("",)))
		if others:
			bad.append({"closing": c, "also_holds": others})
	return bad


def _cancel(doctype, name):
	doc = frappe.get_doc(doctype, name)
	if doc.docstatus == 1:
		doc.flags.ignore_permissions = True
		doc.cancel()
		return "cancelled"
	return "docstatus %s, left" % doc.docstatus


def run(dry=False, cutoff=None):
	frappe.set_user("Administrator")
	cutoff = cutoff or CUTOFF
	pos, sales, logs, closings, checks = _targets(cutoff)
	plan = {"cutoff": cutoff, "pos_invoices": pos, "sales_invoices": sales,
			"merge_logs": logs, "closing_entries": closings, "checks": checks,
			"waiters": [w for w in WAITERS if frappe.db.exists("Restaurant Waiter", w)]}
	if not pos:
		print("PURGE nothing before %s; already clean" % cutoff)
		return

	mixed = _guard_real_trading(closings, [p["name"] for p in pos])
	if mixed:
		print("REFUSED " + json.dumps(mixed, default=str))
		print("A closing entry from the setup days also banked a real sale. Nothing was"
			  " touched — removing it would take live trading with it.")
		return

	print("PLAN " + json.dumps(plan, default=str))
	if dry:
		print("DRY RUN — nothing changed")
		return

	# the till's own guards exist to stop exactly this; lifted only for this purge
	frappe.flags.rm_test_teardown = True
	done = {"cancelled": [], "deleted": []}

	# cancelling the closing entry unconsolidates, cancels the merge log and its
	for c in closings:
		done["cancelled"].append({"POS Closing Entry": c, "result": _cancel("POS Closing Entry", c)})
	frappe.db.commit()

	for p in pos:
		if frappe.db.exists("POS Invoice", p["name"]):
			done["cancelled"].append({"POS Invoice": p["name"],
									  "result": _cancel("POS Invoice", p["name"])})
	frappe.db.commit()

	for dt, names in (("POS Invoice Merge Log", logs), ("Sales Invoice", sales),
					  ("POS Invoice", [p["name"] for p in pos]),
					  ("POS Closing Entry", closings), ("Table Order", checks)):
		for name in names:
			if not frappe.db.exists(dt, name):
				continue
			try:
				doc = frappe.get_doc(dt, name)
				if doc.docstatus == 1:
					doc.flags.ignore_permissions = True
					doc.cancel()
				frappe.delete_doc(dt, name, force=1, ignore_permissions=True)
				done["deleted"].append({dt: name})
			except Exception as e:
				done["deleted"].append({dt: name, "refused": str(e)[:140]})
		frappe.db.commit()

	for w in plan["waiters"]:
		try:
			frappe.delete_doc("Restaurant Waiter", w, force=1, ignore_permissions=True)
			done["deleted"].append({"Restaurant Waiter": w})
		except Exception as e:
			done["deleted"].append({"Restaurant Waiter": w, "refused": str(e)[:140]})
	frappe.db.commit()
	frappe.flags.rm_test_teardown = False

	print("PURGED " + json.dumps(done, default=str))
	left, _, _, _, _ = _targets(cutoff)
	print("LEFT_BEFORE_CUTOFF " + str(len(left)))
	print("SERIES_AFTER " + json.dumps(frappe.db.sql(
		"select name, `current` from tabSeries where name in "
		"('ACC-PSINV-2026-','ACC-SINV-2026-','POS-CLO-2026-','OR-2026-')", as_dict=True), default=str))
	print("EARLIEST_SALE " + json.dumps(frappe.db.sql(
		"select min(posting_date) d, count(*) n, sum(grand_total) t from `tabPOS Invoice`"
		" where docstatus = 1", as_dict=True), default=str))
