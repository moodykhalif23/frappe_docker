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


WAITER_FIELD = {"fieldname": "waiter", "fieldtype": "Link", "options": "Restaurant Waiter", "label": "Waiter"}


def ensure_custom_fields():
	"""Idempotent: hangs the waiter link on the table, its orders and its invoices."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields({
		"Restaurant Object": [dict(WAITER_FIELD, insert_after="current_user")],
		"Table Order": [dict(WAITER_FIELD, insert_after="customer")],
		"POS Invoice": [dict(WAITER_FIELD, insert_after="customer", read_only=1)],
	}, ignore_validate=True)
	frappe.db.commit()
	return "ok"


def _initials(name):
	parts = [p for p in (name or "").split() if p]
	if len(parts) > 1:
		return (parts[0][0] + parts[-1][0]).upper()
	return (parts[0][:2].upper() if parts else "?")


@frappe.whitelist()
def waiters():
	"""The active waiters, for the terminal's name pad. Never returns PINs."""
	rows = frappe.get_all(
		"Restaurant Waiter",
		filters={"active": 1},
		fields=["name", "waiter_name", "colour"],
		order_by="waiter_name",
	)
	for r in rows:
		r["initials"] = _initials(r["waiter_name"])
	return rows


def _verify_pin(waiter, pin):
	import hmac

	from frappe.utils.password import get_decrypted_password

	row = frappe.db.get_value("Restaurant Waiter", waiter, ["name", "waiter_name", "active"], as_dict=True)
	if not row:
		frappe.throw(frappe._("Unknown waiter"))
	if not row.active:
		frappe.throw(frappe._("{0} is not on the active list").format(row.waiter_name))

	stored = get_decrypted_password("Restaurant Waiter", waiter, "pin", raise_exception=False)
	if not stored or not hmac.compare_digest(str(pin).strip(), str(stored)):
		frappe.throw(frappe._("Wrong PIN"))
	return row


def _token_key(waiter):
	return "rm_waiter_token:{0}:{1}".format(frappe.session.user, waiter)


def _authorised(waiter, pin=None, token=None):
	# A PIN is tapped once per shift on the terminal; the token stands in for it
	# afterwards so claiming a table is one tap, not a PIN every time.
	if pin:
		return _verify_pin(waiter, pin)
	if token and frappe.cache().get_value(_token_key(waiter)) == token:
		return frappe.db.get_value("Restaurant Waiter", waiter, ["name", "waiter_name", "active"], as_dict=True)
	frappe.throw(frappe._("Tap your PIN to sign in first"))


@frappe.whitelist()
def waiter_sign_in(waiter, pin):
	"""Sign a waiter on to this terminal for the shift."""
	row = _verify_pin(waiter, pin)
	token = frappe.generate_hash(length=32)
	frappe.cache().set_value(_token_key(waiter), token, expires_in_sec=12 * 60 * 60)
	return {
		"waiter": row.name,
		"waiter_name": row.waiter_name,
		"initials": _initials(row.waiter_name),
		"token": token,
	}


@frappe.whitelist()
def claim_table(table, waiter, pin=None, token=None):
	"""Give a table to a waiter — Toast's 'change server', one owner per table."""
	row = _authorised(waiter, pin, token)

	if not frappe.db.exists("Restaurant Object", table):
		frappe.throw(frappe._("Unknown table"))

	frappe.db.set_value("Restaurant Object", table, "waiter", waiter)
	for order in frappe.get_all(
		"Table Order", filters={"table": table, "status": ["not in", ["Cancelled", "Invoiced"]]}
	):
		frappe.db.set_value("Table Order", order.name, "waiter", waiter)
	frappe.db.commit()

	return {"waiter": waiter, "waiter_name": row.waiter_name, "initials": _initials(row.waiter_name)}


@frappe.whitelist()
def floor_waiters():
	"""Which waiter holds which table, for the floor's badges."""
	rows = frappe.get_all("Restaurant Object", filters={"type": "Table"}, fields=["name", "waiter"])
	colours = {w.name: w.colour for w in frappe.get_all("Restaurant Waiter", fields=["name", "colour"])}
	return {
		r.name: {"waiter": r.waiter, "initials": _initials(r.waiter), "colour": colours.get(r.waiter) or "#4b5563"}
		for r in rows if r.waiter
	}
