"""A fingerprint of the live business data as it stood at a moment, so a deploy can be
proved to have changed none of it. Read-only: it runs only SELECTs.

    ssh <host> "docker exec -i <backend> bash -lc 'cat > /tmp/fp.py'" \
        < restaurant/prod_fingerprint.py
    ssh <host> "echo 'exec(open(\"/tmp/fp.py\").read(), globals()); run(\"<as_of>\")' \
        | docker exec -i <backend> bench --site <site> console"

Everything counted, summed and hashed is bounded by `as_of` (a timestamp), so a
restaurant that keeps trading through the deploy does not move the number. Take the
first fingerprint, note the as_of it prints, then pass that same as_of afterwards: the
FINGERPRINT line must be identical. If it is not, the deploy rewrote history.

Series and live row counts are reported separately, unhashed — those move with ordinary
trading and are there to be read, not matched.
"""
import hashlib
import json

import frappe

COUNTS = [
	"GL Entry", "POS Invoice", "Sales Invoice", "POS Invoice Item", "Sales Invoice Item",
	"Sales Invoice Payment", "POS Closing Entry", "POS Opening Entry", "POS Invoice Merge Log",
	"Table Order", "Order Entry Item", "Restaurant Booking", "Restaurant Object",
	"Restaurant Waiter", "Employee", "Employee Checkin", "Customer", "Item", "Item Price",
	"Stock Ledger Entry", "Stock Entry", "Payment Entry", "Journal Entry",
]

SUMS = [
	("GL Entry", "debit"), ("GL Entry", "credit"),
	("POS Invoice", "grand_total"), ("Sales Invoice", "grand_total"),
	("Table Order", "amount"), ("Order Entry Item", "qty"),
	("Stock Ledger Entry", "actual_qty"),
]

# row-level, so a rewritten total is caught even when counts and sums happen to agree
CONTENT = [
	("GL Entry", ["name", "debit", "credit", "account", "is_cancelled"]),
	("POS Invoice", ["name", "grand_total", "docstatus", "status", "waiter"]),
	("Sales Invoice", ["name", "grand_total", "docstatus", "status"]),
	("POS Closing Entry", ["name", "docstatus", "grand_total"]),
	("Table Order", ["name", "status", "amount", "waiter", "link_invoice"]),
]


def _hashed(as_of):
	out = {"counts": {}, "sums": {}, "content": {}}
	for dt in COUNTS:
		try:
			out["counts"][dt] = frappe.db.sql(
				"select count(*) from `tab%s` where creation <= %%s" % dt, as_of)[0][0]
		except Exception as e:
			out["counts"][dt] = "n/a:%s" % str(e)[:40]
	for dt, field in SUMS:
		try:
			val = frappe.db.sql("select coalesce(sum(`%s`), 0) from `tab%s` where creation <= %%s"
								% (field, dt), as_of)[0][0]
			out["sums"]["%s.%s" % (dt, field)] = round(float(val or 0), 4)
		except Exception as e:
			out["sums"]["%s.%s" % (dt, field)] = "n/a:%s" % str(e)[:40]
	for dt, fields in CONTENT:
		try:
			cols = ", ".join("`%s`" % f for f in fields)
			rows = frappe.db.sql("select %s from `tab%s` where creation <= %%s order by name"
								 % (cols, dt), as_of)
			blob = json.dumps(rows, sort_keys=True, default=str)
			out["content"][dt] = "%s:%s" % (len(rows), hashlib.sha256(blob.encode()).hexdigest()[:32])
		except Exception as e:
			out["content"][dt] = "n/a:%s" % str(e)[:40]
	return out


def run(as_of=None):
	as_of = as_of or str(frappe.utils.now_datetime())[:19]
	snap = _hashed(as_of)
	blob = json.dumps(snap, sort_keys=True, default=str)
	print("AS_OF " + as_of)
	print("FINGERPRINT " + hashlib.sha256(blob.encode()).hexdigest())
	print("HASHED " + blob)

	live = {"series": {}, "now_counts": {}}
	for row in frappe.db.sql("select name, `current` from tabSeries order by name", as_dict=True):
		live["series"][row["name"]] = row["current"]
	for dt in ("POS Invoice", "Table Order", "GL Entry", "Employee Checkin"):
		live["now_counts"][dt] = frappe.db.count(dt)
	print("LIVE " + json.dumps(live, sort_keys=True, default=str))
