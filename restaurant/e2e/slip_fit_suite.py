"""The 80mm slips: frappe's own table CSS puts 10px on every cell, which doubled
the height of every receipt, and `table-layout: auto` ignored the column widths so
dish names wrapped and pushed the slip onto a second page. Both are guarded here,
along with the fitted page height. Read-only: it renders, it writes nothing."""
import re
import frappe

PASSED = []


def ok(name, cond, detail=""):
	PASSED.append(bool(cond))
	print("%s  %s%s" % ("PASS" if cond else "FAIL", name, ("   [%s]" % detail) if detail else ""))


def _page_mm(html):
	m = re.search(r"@page \{ size: 80mm (\d+(?:\.\d+)?)mm; margin: 0 \}", html)
	return float(m.group(1)) if m else 0


def run():
	frappe.set_user("Administrator")
	rec = frappe.db.get_value("Print Format", "Etham Receipt", "html") or ""
	day = frappe.db.get_value("Print Format", "Etham Day Report", "html") or ""
	ok("the receipt is installed", bool(re.search(r"rm_receipt_v\d+", rec)), rec[:60])
	ok("the day report is installed", bool(re.search(r"rm_day_report_v\d+", day)), day[:60])

	# --- the two faults that fed a second page ---
	for label, html in (("receipt", rec), ("day report", day)):
		ok("%s says its cell padding louder than frappe's 10px" % label,
		   bool(re.search(r"\.rm-[rd] td[^{]*\{[^}]*padding:[^;}]*!important", html)), label)
		ok("%s fixes its column widths, so a long dish name cannot widen a column" % label,
		   "table-layout: fixed" in html, label)

	# --- the height is explicit, and grows with the bill ---
	inv = frappe.get_all("POS Invoice", filters={"docstatus": 1}, order_by="creation desc",
						 limit=1, pluck="name")
	if inv:
		html = frappe.get_print("POS Invoice", inv[0], "Etham Receipt")
		h = _page_mm(html)
		n = len(frappe.get_doc("POS Invoice", inv[0]).items)
		ok("a real bill gets an explicit page height, never 'auto'",
		   h > 0 and "80mm auto" not in html, "%smm" % h)
		# fitted at 4.49mm a row over an 18.7mm frame, plus slack
		ok("and that height matches what the rows need", 23 + 4 * n <= h <= 60 + 9 * n,
		   "%d dishes -> %smm" % (n, h))

	# --- a dish name too long for the column is counted as the extra row it draws ---
	ok("a wrapped dish name is counted", "_wrapped" in rec and "item_name" in rec)

	print("%d/%d passed" % (sum(PASSED), len(PASSED)))
	if not all(PASSED):
		raise AssertionError("slip fit suite failed")
