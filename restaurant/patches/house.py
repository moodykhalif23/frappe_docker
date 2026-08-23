# Floor operations this fork adds on top of restaurant_management.
# COPY'd whole into the app, so a rebake always lands the current version.

import frappe
from frappe.utils import get_date_str, today


@frappe.whitelist()
def house_shift(pos_profile=None):
	"""The open shift the whole floor bills into.

	erpnext validates billing against the newest open POS Opening Entry *per
	profile* (sales_invoice.validate_pos_opening_entry), so we look it up the
	same way; the stock POS check filters by session user instead and strands
	every waiter who did not open the shift behind an unusable create dialog.
	"""
	filters = {"status": "Open"}
	if pos_profile:
		filters["pos_profile"] = pos_profile

	entries = frappe.get_all(
		"POS Opening Entry",
		filters=filters,
		fields=["name", "company", "pos_profile", "period_start_date", "user"],
		order_by="period_start_date desc",
	)
	if not entries:
		return None

	shift = entries[0]
	# erpnext refuses to bill unless exactly one open entry exists, dated today.
	shift["conflicts"] = len(entries) - 1
	shift["stale"] = 0 if get_date_str(shift["period_start_date"]) == today() else 1
	return shift


def _table_busy(table, company):
	# Mirrors Restaurant Object.orders_count so "free" means what the floor shows.
	return bool(frappe.db.count("Table Order", {
		"table": table,
		"company": company,
		"show_in_pos": 1,
		"status": ["not in", ["Cancelled", "Invoiced", "Opened"]],
	}))


def _table_seated(table):
	# A party is seated the moment it is booked, but the floor only counts a table
	# busy once items are on the order — without this the host can double-seat it.
	return bool(frappe.db.count("Restaurant Booking", {
		"table": table,
		"status": "Open",
		"reservation_end_time": [">", frappe.utils.now_datetime()],
	}))


@frappe.whitelist()
def free_tables(covers=0, room=None):
	"""Tables that can seat the party and have nothing open on them."""
	covers = int(covers or 0)
	filters = {"type": "Table"}
	if room:
		filters["room"] = room

	out = []
	for t in frappe.get_all(
		"Restaurant Object",
		filters=filters,
		fields=["name", "description", "no_of_seats", "minimum_seating", "room", "company"],
		order_by="description",
	):
		seats = t.no_of_seats or 0
		# A table with no capacity recorded is still offered, but last and labelled:
		# bad data should not hide a usable table, nor pretend it fits a coach party.
		if covers and seats and seats < covers:
			continue
		if _table_busy(t.name, t.company) or _table_seated(t.name):
			continue
		out.append({
			"name": t.name,
			"description": t.description or t.name,
			"seats": seats,
			"room": t.room,
			"fits": bool(seats) and (not covers or seats >= covers),
		})

	# Smallest table that fits first — don't burn a six-top on a couple.
	out.sort(key=lambda t: (not t["fits"], t["seats"] or 9999, t["description"]))
	return out


def _walkin_customer(guest_name, contact=None):
	# Reused by exact name so regulars don't breed duplicate Customers, but the
	# host never has to search: typing the name is the whole interaction.
	existing = frappe.db.get_value("Customer", {"customer_name": guest_name}, "name")
	if existing:
		return existing

	doc = frappe.new_doc("Customer")
	doc.customer_name = guest_name
	doc.customer_group = frappe.db.get_value("Customer Group", {"is_group": 0})
	doc.territory = frappe.db.get_value("Territory", {"is_group": 0})
	doc.mobile_no = contact
	doc.insert(ignore_permissions=True)
	return doc.name


@frappe.whitelist()
def seat_walkin(guest_name, covers=1, table=None, contact=None):
	"""Seat a walk-in: a name goes in, a party is seated on a table.

	The stock check-in demands an existing Customer and a reservation window,
	which is backwards for the walk-in that is most of a restaurant's service.
	"""
	guest_name = (guest_name or "").strip()
	if not guest_name:
		frappe.throw(frappe._("A guest name is required"))
	if not table:
		frappe.throw(frappe._("Pick a table"))

	obj = frappe.db.get_value("Restaurant Object", table, ["name", "room", "company"], as_dict=True)
	if not obj:
		frappe.throw(frappe._("That table no longer exists"))
	if _table_busy(obj.name, obj.company) or _table_seated(obj.name):
		frappe.throw(frappe._("That table was just taken — pick another"))

	now = frappe.utils.now_datetime()
	booking = frappe.get_doc({
		"doctype": "Restaurant Booking",
		"customer": _walkin_customer(guest_name, contact),
		"contact_number": contact,
		"no_of_people": int(covers or 1),
		"reservation_time": now,
		"reservation_end_time": frappe.utils.add_to_date(now, hours=2),
		"table": obj.name,
		"status": "Open",
		"company": obj.company,
	})
	booking.insert(ignore_permissions=True)

	return {"booking": booking.name, "customer": booking.customer, "table": obj.name, "room": obj.room}
