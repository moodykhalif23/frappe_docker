"""The waiter drill-down must agree with the summary it drills into, or the figures
argue with each other in front of the manager. Read-only: it opens both reports through
the desk's own path and writes nothing.
"""
import json
import frappe

PASSED = []
SUMMARY = "Sales by Waiter"
BOOK = "Waiter Day Book"


def ok(name, cond, detail=""):
	PASSED.append(bool(cond))
	print("%s  %s%s" % ("PASS" if cond else "FAIL", name, ("   [%s]" % detail) if detail else ""))


def run_report(name, filters):
	"""Through frappe.desk.query_report.run — the path the desk takes, not an import."""
	from frappe.desk.query_report import run
	res = run(name, filters=json.dumps(filters), ignore_prepared_report=True)
	return res.get("result") or []


def keyed(rows, field="waiter"):
	return {r.get(field): r for r in rows if isinstance(r, dict)}


def run():
	frappe.set_user("Administrator")
	to_date = frappe.utils.today()
	from_date = frappe.utils.add_days(to_date, -60)
	base = {"from_date": from_date, "to_date": to_date}

	ok("the day book is registered as a script report",
	   frappe.db.get_value("Report", BOOK, "report_type") == "Script Report",
	   str(frappe.db.get_value("Report", BOOK, "report_type")))
	ok("its module folder matches frappe.scrub of its name",
	   frappe.scrub(BOOK) == "waiter_day_book", frappe.scrub(BOOK))

	# --- the money view must equal the summary it drills into, waiter by waiter ---
	summary = keyed(run_report(SUMMARY, dict(base, credit="Check owner")))
	ok("the summary returns rows to drill into", bool(summary), json.dumps(sorted(summary))[:120])

	checked = 0
	for waiter, srow in summary.items():
		if waiter == "Unassigned":
			continue
		rows = run_report(BOOK, dict(base, waiter=waiter, view="Per check", include="Billed only"))
		total = sum(frappe.utils.flt(r.get("amount")) for r in rows)
		ok("per check, %s totals what the summary says" % waiter,
		   abs(total - frappe.utils.flt(srow.get("sales"))) < 0.01,
		   "book %s vs summary %s over %d row(s)" % (total, srow.get("sales"), len(rows)))
		ok("and bills the same number of checks for %s" % waiter,
		   len(rows) == frappe.utils.cint(srow.get("checks")),
		   "book %d vs summary %s" % (len(rows), srow.get("checks")))
		checked += 1
		if checked >= 3:
			break
	ok("at least one waiter was reconciled", checked > 0, "waiters=%d" % checked)

	# --- the food view must equal the summary's other basis ---
	fired = keyed(run_report(SUMMARY, dict(base, credit="Lines fired")))
	done = 0
	for waiter, srow in fired.items():
		if waiter == "Unassigned":
			continue
		rows = run_report(BOOK, dict(base, waiter=waiter, view="Per item", include="Billed only"))
		total = sum(frappe.utils.flt(r.get("amount")) for r in rows)
		ok("per item, %s totals what Lines fired says" % waiter,
		   abs(total - frappe.utils.flt(srow.get("sales"))) < 0.01,
		   "book %s vs summary %s over %d line(s)" % (total, srow.get("sales"), len(rows)))
		done += 1
		if done >= 3:
			break
	ok("at least one waiter was reconciled on lines", done > 0, "waiters=%d" % done)

	# --- the columns the request asked for are actually there ---
	any_waiter = next((w for w in summary if w != "Unassigned"), None)
	if any_waiter:
		rows = run_report(BOOK, dict(base, waiter=any_waiter, view="Per item"))
		if rows:
			r = rows[0]
			for field in ("time", "check_id", "table_name", "covers", "item", "qty", "amount", "invoice"):
				ok("a line carries its %s" % field, field in r, json.dumps(sorted(r))[:160])
			ok("every line belongs to the waiter asked for",
			   all(x.get("waiter") == any_waiter for x in rows),
			   json.dumps(sorted({x.get("waiter") for x in rows}))[:120])
			ok("the lines come back in time order",
			   [x.get("time") for x in rows] == sorted(x.get("time") for x in rows))

	# --- a filter that matches nobody returns nothing, rather than everybody ---
	empty = run_report(BOOK, dict(base, waiter="ZZ No Such Waiter", view="Per item"))
	ok("an unknown waiter returns an empty book, not the whole floor", empty == [],
	   json.dumps(empty)[:120])

	# --- open checks appear only when asked for ---
	billed = run_report(BOOK, dict(base, view="Per check", include="Billed only"))
	everything = run_report(BOOK, dict(base, view="Per check", include="Billed and open"))
	ok("every billed row carries its invoice", all(r.get("invoice") for r in billed),
	   json.dumps([r for r in billed if not r.get("invoice")])[:160])
	ok("asking for open checks can only add rows, never remove them",
	   len(everything) >= len(billed), "billed=%d everything=%d" % (len(billed), len(everything)))

	print("%d/%d passed" % (sum(PASSED), len(PASSED)))
	if not all(PASSED):
		raise AssertionError("waiter day book suite failed")
