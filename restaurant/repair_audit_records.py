"""One-off audit repairs on a live site. Safe to re-run: each part selects only rows
still carrying the fault, so a second run finds nothing and changes nothing.

    ssh <host> "docker exec -i <backend> bash -lc 'cat > /tmp/repair.py'" \
        < restaurant/repair_audit_records.py
    ssh <host> "echo 'exec(open(\"/tmp/repair.py\").read(), globals()); run()' \
        | docker exec -i <backend> bench --site <site> console"

Two faults, both found on frappe.ikobriq.com on 2026-09-09:

1. A closing entry's reconciliation row carried a non-cash "opening float". The site
   opens each day with the M-Pesa till balance typed into that box, and an earlier
   build counted it as money in the drawer — so POS-CLO-2026-00016 claimed a
   difference of -71,396 against a count nobody took. This table is a reconciliation
   record, not a posting, so correcting it moves no ledger entry.

2. A check reading Invoiced against an invoice that had since been deleted, claiming a
   sale no invoice can support. Cancelled, not deleted: deleting would hand its number
   back to the next check, which is the fault being fixed everywhere else.

Every change is recorded as a comment on the document it touches.
"""
import json

import frappe


def _cash_modes():
	return {m.name for m in frappe.get_all("Mode of Payment", filters={"type": "Cash"},
										   fields=["name"])}


def _repair_false_variance(audit):
	cash = tuple(_cash_modes()) or ("",)
	rows = frappe.db.sql("""
		select d.name as row, d.parent, d.mode_of_payment, d.opening_amount,
			   d.expected_amount, d.closing_amount, d.difference
		from `tabPOS Closing Entry Detail` d
		where d.opening_amount != 0 and d.mode_of_payment not in %(cash)s
	""", {"cash": cash}, as_dict=True)
	for r in rows:
		sales = frappe.utils.flt(r.expected_amount) - frappe.utils.flt(r.opening_amount)
		counted = frappe.utils.flt(r.closing_amount)
		# a row left at zero was never counted, and erpnext leaves such a row's difference at zero
		diff = (counted - sales) if counted else 0.0
		frappe.db.set_value("POS Closing Entry Detail", r.row,
							{"opening_amount": 0, "expected_amount": sales, "difference": diff},
							update_modified=False)
		frappe.get_doc("POS Closing Entry", r.parent).add_comment("Comment", frappe._(
			"Corrected the {0} reconciliation row. It carried an opening float of {1} — the till"
			" balance recorded on the opening entry, not money in the drawer — so this entry"
			" claimed a difference of {2} against a count nobody took. The row now reads expected"
			" {3}, difference {4}. No ledger entry was affected: this table is a reconciliation"
			" record, not a posting."
		).format(r.mode_of_payment, frappe.utils.fmt_money(r.opening_amount),
				 frappe.utils.fmt_money(r.difference), frappe.utils.fmt_money(sales),
				 frappe.utils.fmt_money(diff)))
		audit["closing_rows"].append({
			"entry": r.parent, "mode": r.mode_of_payment,
			"was": {"opening": r.opening_amount, "expected": r.expected_amount,
					"difference": r.difference},
			"now": {"opening": 0.0, "expected": sales, "difference": diff}})


def _repair_orphan_checks(audit):
	orph = frappe.db.sql("""
		select o.name, o.status, o.link_invoice, o.customer, o.amount, o.table
		from `tabTable Order` o
		where o.link_invoice is not null and o.link_invoice != ''
		  and not exists (select 1 from `tabPOS Invoice` i where i.name = o.link_invoice)
		  and not exists (select 1 from `tabSales Invoice` s where s.name = o.link_invoice)
	""", as_dict=True)
	for o in orph:
		lines = frappe.db.count("Order Entry Item", {"parent": o.name, "qty": [">", 0]})
		frappe.db.set_value("Table Order", o.name,
							{"status": "Cancelled", "link_invoice": None, "show_in_pos": 0},
							update_modified=False)
		frappe.get_doc("Table Order", o.name).add_comment("Comment", frappe._(
			"Cancelled during an audit clean-up. This check read {0} against invoice {1}, which had"
			" been deleted, so it claimed a sale no invoice could support. Cancelling drops the"
			" claim and keeps the record: {2}, {3}, {4} item line(s) still listed. It was not"
			" deleted, because deleting would hand its number back to the next check."
		).format(o.status, o.link_invoice, o.customer or frappe._("no guest name"),
				 frappe.utils.fmt_money(o.amount), lines))
		audit["orphan_checks"].append({"check": o.name, "was_status": o.status,
									   "dangling_invoice": o.link_invoice, "table": o.table,
									   "amount": o.amount, "lines_kept": lines})


def run():
	audit = {"closing_rows": [], "orphan_checks": []}
	_repair_false_variance(audit)
	_repair_orphan_checks(audit)
	frappe.db.commit()
	print("REPAIRED", json.dumps(audit, default=str))

	cash = tuple(_cash_modes()) or ("",)
	print("LEFT_FALSE_VARIANCE", frappe.db.sql("""
		select count(*) from `tabPOS Closing Entry Detail`
		where opening_amount != 0 and mode_of_payment not in %(cash)s
	""", {"cash": cash})[0][0])
	print("LEFT_ORPHAN_CHECKS", frappe.db.sql("""
		select count(*) from `tabTable Order` o
		where o.link_invoice is not null and o.link_invoice != ''
		  and not exists (select 1 from `tabPOS Invoice` i where i.name = o.link_invoice)
		  and not exists (select 1 from `tabSales Invoice` s where s.name = o.link_invoice)
	""")[0][0])
