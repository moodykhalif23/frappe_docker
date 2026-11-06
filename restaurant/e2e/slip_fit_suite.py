"""The 80mm slips: frappe's own table CSS puts 10px on every cell, which doubled
the height of every receipt, and `table-layout: auto` ignored the column widths so
dish names wrapped and pushed the slip onto a second page. Both are guarded here,
along with the page rule proven on the till's printer: 80mm wide, auto height.
Read-only: it renders, it writes nothing."""
import re
import frappe

PASSED = []
AUTO_PAGE = "@page { size: 80mm auto; margin: 0 }"
COMPUTED_PAGE = re.compile(r"size: 80mm \d+(?:\.\d+)?mm")


def ok(name, cond, detail=""):
	PASSED.append(bool(cond))
	print("%s  %s%s" % ("PASS" if cond else "FAIL", name, ("   [%s]" % detail) if detail else ""))


def _page_rule(html):
	m = re.search(r"@page \{[^}]*80mm[^}]*\}", html)
	return m.group(0) if m else "no 80mm @page rule"


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

	# --- the page sizes to the roll: 80mm wide, auto height ---
	# The till's CITIZEN CT-S300 driver offers discrete paper sizes. A computed
	# height such as `80mm 59mm` matches none, so Chrome under --kiosk-printing fell
	# back to the 3.27m default roll (21 Sep 2026); `80mm auto` sizes to the roll and
	# cuts cleanly. Proven on the till: restaurant/patches/receipt_80mm_auto.py.
	inv = frappe.get_all("POS Invoice", filters={"docstatus": 1}, order_by="creation desc",
						 limit=1, pluck="name")
	if inv:
		html = frappe.get_print("POS Invoice", inv[0], "Etham Receipt")
		ok("a real bill's page is 80mm wide, auto height, no margin", AUTO_PAGE in html, _page_rule(html))
		ok("and never a computed height, which the till's driver has no paper for",
		   not COMPUTED_PAGE.search(html), _page_rule(html))
		# the print head reaches only ~4-76mm of the roll; text is kept to 6-74mm
		ok("its text is centred under the 72mm print head", "rm_printable_72mm" in html)

	# --- a dish name too long for the column is counted as the extra row it draws ---
	ok("a wrapped dish name is counted", "_wrapped" in rec and "item_name" in rec)

	print("%d/%d passed" % (sum(PASSED), len(PASSED)))
	if not all(PASSED):
		raise AssertionError("slip fit suite failed")
