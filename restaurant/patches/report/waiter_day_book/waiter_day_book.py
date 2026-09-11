# One waiter's day, line by line. Read-only: it writes nothing, anywhere.

import frappe
from frappe.utils import flt

UNASSIGNED = "Unassigned"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if filters.get("view") == "Per check":
		return check_columns(), check_rows(filters)
	return item_columns(), item_rows(filters)


def item_columns():
	return [
		{"label": "Time", "fieldname": "time", "fieldtype": "Datetime", "width": 150},
		{"label": "Waiter", "fieldname": "waiter", "fieldtype": "Link", "options": "Restaurant Waiter", "width": 110},
		{"label": "Check", "fieldname": "check_id", "fieldtype": "Link", "options": "Table Order", "width": 130},
		{"label": "Table", "fieldname": "table_name", "fieldtype": "Data", "width": 90},
		{"label": "Guest", "fieldname": "guest", "fieldtype": "Data", "width": 120},
		{"label": "Seats", "fieldname": "covers", "fieldtype": "Int", "width": 60},
		{"label": "Item", "fieldname": "item", "fieldtype": "Data", "width": 180},
		{"label": "Qty", "fieldname": "qty", "fieldtype": "Float", "width": 60, "precision": 2},
		{"label": "Rate", "fieldname": "rate", "fieldtype": "Currency", "width": 100},
		{"label": "Amount", "fieldname": "amount", "fieldtype": "Currency", "width": 110},
		{"label": "Line", "fieldname": "line_status", "fieldtype": "Data", "width": 90},
		{"label": "Check status", "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": "Invoice", "fieldname": "invoice", "fieldtype": "Link", "options": "POS Invoice", "width": 160},
	]


def check_columns():
	return [
		{"label": "Paid", "fieldname": "time", "fieldtype": "Datetime", "width": 150},
		{"label": "Opened", "fieldname": "opened", "fieldtype": "Datetime", "width": 150},
		{"label": "Waiter", "fieldname": "waiter", "fieldtype": "Link", "options": "Restaurant Waiter", "width": 110},
		{"label": "Checks", "fieldname": "check_id", "fieldtype": "Data", "width": 150},
		{"label": "Tables", "fieldname": "table_name", "fieldtype": "Data", "width": 110},
		{"label": "Guest", "fieldname": "guest", "fieldtype": "Data", "width": 130},
		{"label": "Seats", "fieldname": "covers", "fieldtype": "Int", "width": 60},
		{"label": "Items", "fieldname": "items", "fieldtype": "Int", "width": 60},
		{"label": "Amount", "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": "Invoice", "fieldname": "invoice", "fieldtype": "Link", "options": "POS Invoice", "width": 160},
	]


def _waiter_clause(expr, filters, values):
	"""Match the filter against the attributed waiter, Unassigned included."""
	if not filters.get("waiter"):
		return None
	values["waiter"] = filters.waiter
	return "%s = %%(waiter)s" % expr


def item_rows(filters):
	"""Every line the waiter sent, credited to whoever fired it, then to the check's
	owner. Same source and formula as Sales by Waiter's 'Lines fired'."""
	credited = "coalesce(nullif(e.waiter, ''), nullif(o.waiter, ''), '%s')" % UNASSIGNED
	conds = ["e.qty > 0"]
	values = {}
	if filters.get("include") != "Billed and open":
		conds.append("o.status = 'Invoiced'")
	else:
		conds.append("o.status != 'Cancelled'")
	if filters.get("from_date"):
		conds.append("date(o.creation) >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conds.append("date(o.creation) <= %(to_date)s")
		values["to_date"] = filters.to_date
	if filters.get("room"):
		conds.append("o.room = %(room)s")
		values["room"] = filters.room
	if filters.get("pos_profile"):
		conds.append("o.pos_profile = %(pos_profile)s")
		values["pos_profile"] = filters.pos_profile
	who = _waiter_clause(credited, filters, values)
	if who:
		conds.append(who)

	rows = frappe.db.sql(
		"""
		select
			coalesce(e.ordered_time, o.creation) as time,
			{credited} as waiter,
			o.name as check_id,
			coalesce(nullif(t.description, ''), o.`table`) as table_name,
			o.customer as guest,
			coalesce(o.dinners, 0) as covers,
			coalesce(nullif(e.item_name, ''), e.item_code) as item,
			e.qty as qty,
			e.rate as rate,
			e.qty * e.rate as amount,
			e.status as line_status,
			o.status as status,
			o.link_invoice as invoice
		from `tabOrder Entry Item` e
		join `tabTable Order` o on o.name = e.parent
		left join `tabRestaurant Object` t on t.name = o.`table`
		where {conds}
		order by time, o.name
		""".format(credited=credited, conds=" and ".join(conds)),
		values,
		as_dict=True,
	)
	for r in rows:
		r["amount"] = flt(r["amount"])
	return rows


def check_rows(filters):
	"""One row per bill, credited to the invoice's waiter. Same source and figure as
	Sales by Waiter's 'Check owner', so the totals agree row for row."""
	conds = ["i.docstatus = 1"]
	values = {}
	if filters.get("from_date"):
		conds.append("i.posting_date >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conds.append("i.posting_date <= %(to_date)s")
		values["to_date"] = filters.to_date
	if filters.get("pos_profile"):
		conds.append("i.pos_profile = %(pos_profile)s")
		values["pos_profile"] = filters.pos_profile
	if filters.get("room"):
		conds.append("i.booking in (select name from `tabRestaurant Booking` where room = %(room)s)")
		values["room"] = filters.room
	credited = "coalesce(nullif(i.waiter, ''), '%s')" % UNASSIGNED
	who = _waiter_clause(credited, filters, values)
	if who:
		conds.append(who)

	# grouped by invoice, so a bill split across two checks is still counted once
	rows = frappe.db.sql(
		"""
		select
			timestamp(i.posting_date, i.posting_time) as time,
			min(o.creation) as opened,
			{credited} as waiter,
			group_concat(distinct o.name order by o.name separator ', ') as check_id,
			group_concat(distinct coalesce(nullif(t.description, ''), o.`table`)
						 order by coalesce(nullif(t.description, ''), o.`table`) separator ', ') as table_name,
			i.customer as guest,
			(select coalesce(sum(coalesce(z.dinners, 0)), 0) from `tabTable Order` z
			  where z.link_invoice = i.name) as covers,
			(select count(*) from `tabOrder Entry Item` x join `tabTable Order` y on y.name = x.parent
			  where y.link_invoice = i.name and x.qty > 0) as items,
			i.grand_total as amount,
			i.status as status,
			i.name as invoice
		from `tabPOS Invoice` i
		left join `tabTable Order` o on o.link_invoice = i.name
		left join `tabRestaurant Object` t on t.name = o.`table`
		where {conds}
		group by i.name
		order by time, i.name
		""".format(credited=credited, conds=" and ".join(conds)),
		values,
		as_dict=True,
	)
	for r in rows:
		r["amount"] = flt(r["amount"])

	if filters.get("include") == "Billed and open":
		rows += _open_checks(filters)
		rows.sort(key=lambda r: (r.get("time") or r.get("opened") or ""))
	return rows


def _open_checks(filters):
	"""Checks still standing, so a day under question shows what never got billed."""
	conds = ["o.status not in ('Invoiced', 'Cancelled')"]
	values = {}
	if filters.get("from_date"):
		conds.append("date(o.creation) >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conds.append("date(o.creation) <= %(to_date)s")
		values["to_date"] = filters.to_date
	if filters.get("room"):
		conds.append("o.room = %(room)s")
		values["room"] = filters.room
	if filters.get("pos_profile"):
		conds.append("o.pos_profile = %(pos_profile)s")
		values["pos_profile"] = filters.pos_profile
	credited = "coalesce(nullif(o.waiter, ''), '%s')" % UNASSIGNED
	who = _waiter_clause(credited, filters, values)
	if who:
		conds.append(who)

	rows = frappe.db.sql(
		"""
		select
			null as time,
			o.creation as opened,
			{credited} as waiter,
			o.name as check_id,
			coalesce(nullif(t.description, ''), o.`table`) as table_name,
			o.customer as guest,
			coalesce(o.dinners, 0) as covers,
			(select count(*) from `tabOrder Entry Item` x
			  where x.parent = o.name and x.qty > 0) as items,
			coalesce(o.amount, 0) as amount,
			o.status as status,
			null as invoice
		from `tabTable Order` o
		left join `tabRestaurant Object` t on t.name = o.`table`
		where {conds}
		order by o.creation
		""".format(credited=credited, conds=" and ".join(conds)),
		values,
		as_dict=True,
	)
	for r in rows:
		r["amount"] = flt(r["amount"])
	return rows
