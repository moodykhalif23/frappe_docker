# Who sold what. Sales and checks come off the invoice; covers and tables off the
# orders, because the invoice has no idea how many people sat down.

import frappe
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return columns(), rows(filters)


def columns():
	return [
		{"label": "Waiter", "fieldname": "waiter", "fieldtype": "Data", "width": 180},
		{"label": "Tables", "fieldname": "tables", "fieldtype": "Int", "width": 80},
		{"label": "Covers", "fieldname": "covers", "fieldtype": "Int", "width": 80},
		{"label": "Checks", "fieldname": "checks", "fieldtype": "Int", "width": 80},
		{"label": "Sales", "fieldname": "sales", "fieldtype": "Currency", "width": 130},
		{"label": "Avg Check", "fieldname": "avg_check", "fieldtype": "Currency", "width": 120},
		{"label": "Per Cover", "fieldname": "per_cover", "fieldtype": "Currency", "width": 120},
	]


def rows(filters):
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
		# the invoice knows its party; the party knows its room
		conds.append("i.booking in (select name from `tabRestaurant Booking` where room = %(room)s)")
		values["room"] = filters.room

	if filters.get("credit") == "Lines fired" and frappe.db.has_column("Order Entry Item", "waiter"):
		# every line carries who fired it: credit the firer, on invoiced checks only
		lconds = ["o.status = 'Invoiced'", "e.qty > 0"]
		lvalues = {}
		if filters.get("from_date"):
			lconds.append("date(o.creation) >= %(from_date)s"); lvalues["from_date"] = filters.from_date
		if filters.get("to_date"):
			lconds.append("date(o.creation) <= %(to_date)s"); lvalues["to_date"] = filters.to_date
		if filters.get("room"):
			lconds.append("o.room = %(room)s"); lvalues["room"] = filters.room
		sales = frappe.db.sql(
			"""
			select coalesce(nullif(e.waiter, ''), coalesce(nullif(o.waiter, ''), 'Unassigned')) as waiter,
				count(distinct o.name) as checks,
				sum(e.qty * e.rate) as sales
			from `tabOrder Entry Item` e
			join `tabTable Order` o on o.name = e.parent
			where {conds}
			group by 1
			""".format(conds=" and ".join(lconds)),
			lvalues,
			as_dict=True,
		)
	else:
		sales = frappe.db.sql(
			"""
			select coalesce(nullif(i.waiter, ''), 'Unassigned') as waiter,
				count(distinct i.name) as checks,
				sum(i.grand_total) as sales
			from `tabPOS Invoice` i
			where {conds}
			group by 1
			""".format(conds=" and ".join(conds)),
			values,
			as_dict=True,
		)

	ocond = ["o.docstatus < 2"]
	ovalues = {}
	if filters.get("from_date"):
		ocond.append("date(o.creation) >= %(from_date)s")
		ovalues["from_date"] = filters.from_date
	if filters.get("to_date"):
		ocond.append("date(o.creation) <= %(to_date)s")
		ovalues["to_date"] = filters.to_date
	if filters.get("room"):
		ocond.append("o.room = %(room)s")
		ovalues["room"] = filters.room

	served = frappe.db.sql(
		"""
		select coalesce(nullif(o.waiter, ''), 'Unassigned') as waiter,
			count(distinct o.table) as tables,
			sum(coalesce(o.dinners, 0)) as covers
		from `tabTable Order` o
		where {conds}
		group by 1
		""".format(conds=" and ".join(ocond)),
		ovalues,
		as_dict=True,
	)
	by_waiter = {r.waiter: r for r in served}

	out = []
	for r in sales:
		extra = by_waiter.pop(r.waiter, None)
		covers = flt(extra.covers) if extra else 0
		out.append({
			"waiter": r.waiter,
			"tables": (extra.tables if extra else 0),
			"covers": covers,
			"checks": r.checks,
			"sales": flt(r.sales),
			"avg_check": flt(r.sales) / r.checks if r.checks else 0,
			"per_cover": flt(r.sales) / covers if covers else 0,
		})

	# Waiters who served but have not billed yet still belong on the sheet.
	for waiter, extra in by_waiter.items():
		out.append({
			"waiter": waiter, "tables": extra.tables, "covers": flt(extra.covers),
			"checks": 0, "sales": 0, "avg_check": 0, "per_cover": 0,
		})

	out.sort(key=lambda r: r["sales"], reverse=True)
	return out
