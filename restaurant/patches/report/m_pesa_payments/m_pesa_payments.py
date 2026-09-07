# Copyright (c) 2026, ikobriq
import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return columns(), rows(filters)


def columns():
	return [
		{"label": _("Paid at"), "fieldname": "paid_at", "fieldtype": "Datetime", "width": 150},
		{"label": _("Code"), "fieldname": "code", "fieldtype": "Data", "width": 130},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Invoice"), "fieldname": "invoice", "fieldtype": "Link", "options": "POS Invoice", "width": 170},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Data", "width": 140},
		{"label": _("Waiter"), "fieldname": "waiter", "fieldtype": "Link", "options": "Restaurant Waiter", "width": 130},
		{"label": _("Cashier"), "fieldname": "cashier", "fieldtype": "Link", "options": "User", "width": 170},
		{"label": _("Mode"), "fieldname": "mode", "fieldtype": "Data", "width": 90},
	]


def rows(filters):
	conds = ["i.docstatus = 1", "p.amount > 0", "lower(replace(p.mode_of_payment, '-', '')) like '%%mpesa%%'"]
	values = {}
	if filters.get("from_date"):
		conds.append("i.posting_date >= %(from_date)s"); values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conds.append("i.posting_date <= %(to_date)s"); values["to_date"] = filters.to_date
	if filters.get("code"):
		conds.append("p.reference_no like %(code)s"); values["code"] = "%%" + filters.code.strip().upper() + "%%"
	if filters.get("waiter"):
		conds.append("i.waiter = %(waiter)s"); values["waiter"] = filters.waiter
	return frappe.db.sql(
		"""
		select timestamp(i.posting_date, i.posting_time) as paid_at,
			coalesce(nullif(p.reference_no, ''), '— no code —') as code,
			p.amount as amount, i.name as invoice, i.customer_name as customer,
			i.waiter as waiter, i.owner as cashier, p.mode_of_payment as mode
		from `tabSales Invoice Payment` p
		join `tabPOS Invoice` i on i.name = p.parent and p.parenttype = 'POS Invoice'
		where {conds}
		order by paid_at desc
		""".format(conds=" and ".join(conds)),
		values,
		as_dict=True,
	)
