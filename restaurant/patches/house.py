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


@frappe.whitelist()
def free_tables(covers=0, room=None, whole_table=0):
	"""Where the party can sit — whole tables, and seats left on shared ones.

	A six-top with two guests has four seats to sell; `whole_table` is for the
	host who wants the table to itself.
	"""
	covers = int(covers or 0)
	whole_table = int(whole_table or 0)
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
		seats = table_seats(t.name, t)
		free = seats["free"]
		if whole_table and seats["occupied"]:
			continue
		# A table with no capacity recorded is still offered, but last and labelled.
		if free is not None:
			if covers and free < covers:
				continue
			if not free:
				continue
		out.append({
			"name": t.name,
			"description": seats["description"],
			"seats": seats["capacity"],
			"free": free,
			"occupied": seats["occupied"],
			"shared": bool(seats["occupied"]),
			"parties": seats["parties"],
			"room": t.room,
			"fits": bool(seats["capacity"]) and (not covers or (free or 0) >= covers),
		})

	# Empty before shared, then the tightest fit.
	out.sort(key=lambda t: (not t["fits"], t["shared"],
							t["free"] if t["free"] is not None else 9999, t["description"]))
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
def seat_walkin(guest_name, covers=1, table=None, contact=None, waiter=None):
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
	_seats_or_throw(obj.name, covers)

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
		"seated_at": now,
		"company": obj.company,
	})
	if waiter and frappe.db.has_column("Restaurant Booking", "waiter"):
		booking.waiter = waiter
	booking.insert(ignore_permissions=True)

	# The pad refuses to open an order until the table carries a customer; on a
	# shared table this is only the default, each check carries its own.
	frappe.db.set_value("Restaurant Object", obj.name, "customer", booking.customer)
	frappe.db.commit()

	order = _open_check(booking, obj)

	return {"booking": booking.name, "customer": booking.customer, "table": obj.name,
			"room": obj.room, "order": order, "seats": table_seats(obj.name)}


WAITER_FIELD = {"fieldname": "waiter", "fieldtype": "Link", "options": "Restaurant Waiter", "label": "Waiter"}
SEATED_FIELD = {"fieldname": "seated_at", "fieldtype": "Datetime", "label": "Seated At", "read_only": 1}
LEFT_FIELD = {"fieldname": "left_at", "fieldtype": "Datetime", "label": "Left At", "read_only": 1}
BOOKING_FIELD = {"fieldname": "booking", "fieldtype": "Link", "options": "Restaurant Booking",
				 "label": "Party", "read_only": 1}


def _ensure_receipt_format():
	"""A receipt that prints clean: browsers draw their URL header in the page
	margin, so a zero-margin format leaves the paper showing only the bill."""
	name = "Etham Receipt"
	if frappe.db.exists("Print Format", name):
		# An earlier build created it without custom_format, which frappe ignores.
		frappe.db.set_value("Print Format", name, "custom_format", 1, update_modified=False)
		return name

	import json
	import os

	src = os.path.join(frappe.get_app_path("erpnext"), "accounts", "print_format",
					   "pos_invoice", "pos_invoice.json")
	html = json.load(open(src))["html"]
	frappe.get_doc({
		"doctype": "Print Format", "name": name, "doc_type": "POS Invoice",
		"module": "Accounts", "print_format_type": "Jinja", "standard": "No",
		"pdf_generator": "wkhtmltopdf", "disabled": 0, "font_size": 12, "custom_format": 1,
		"html": "<style>@page { margin: 0 } .print-format { padding: 6mm 8mm }</style>\n" + html,
	}).insert(ignore_permissions=True)
	return name


def ensure_custom_fields():
	"""Idempotent: hangs the waiter link on the table, its orders and its invoices."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields({
		"Restaurant Object": [dict(WAITER_FIELD, insert_after="current_user")],
		"Table Order": [
			dict(WAITER_FIELD, insert_after="customer"),
			dict(BOOKING_FIELD, insert_after="waiter"),
		],
		"POS Invoice": [
			dict(WAITER_FIELD, insert_after="customer", read_only=1),
			dict(BOOKING_FIELD, insert_after="waiter"),
		],
		"Restaurant Booking": [
			dict(WAITER_FIELD, insert_after="table"),
			dict(SEATED_FIELD, insert_after="reservation_end_time"),
			dict(LEFT_FIELD, insert_after="seated_at"),
		],
	}, ignore_validate=True)

	# The pad's client flow reads these before an item can land; without them a
	# waiter's add-to-cart dies as a silent 403 and the check stays empty.
	from frappe.permissions import add_permission
	for dt in ("Item", "Item Price", "Item Group", "UOM", "POS Profile", "POS Settings",
			   "Stock Settings", "Selling Settings", "Accounts Settings", "Company",
			   "Price List", "Restaurant Settings", "Restaurant Menu", "Mode of Payment",
			   "Sales Taxes and Charges Template", "Account", "Cost Center", "Warehouse",
			   "Customer", "Customer Group", "Territory"):
		try:
			add_permission(dt, "Restaurant User", 0)
		except Exception:
			pass

	# Two parties on one table means two open checks on it.
	frappe.db.set_single_value("Restaurant Settings", "multiple_pending_order", 1)

	receipt = _ensure_receipt_format()
	for p in frappe.get_all("POS Profile", pluck="name"):
		if not frappe.db.get_value("POS Profile", p, "print_format"):
			frappe.db.set_value("POS Profile", p, "print_format", receipt, update_modified=False)

	# frappe 417s a PDF whose print format never chose a generator.
	for pf in frappe.get_all("Print Format", filters={"pdf_generator": ["is", "not set"]}, pluck="name"):
		frappe.db.set_value("Print Format", pf, "pdf_generator", "wkhtmltopdf", update_modified=False)
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
		"checkin": _log_checkin(row.name, "IN"),
	}


@frappe.whitelist()
def claim_table(table, waiter, pin=None, token=None):
	"""Give a table to a waiter — Toast's 'change server', one owner per table."""
	row = _authorised(waiter, pin, token)

	if not frappe.db.exists("Restaurant Object", table):
		frappe.throw(frappe._("Unknown table"))
	if not house_shift():
		frappe.throw(frappe._("The counter is closed. Open the day before claiming tables."))

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


# ---- the door: waitlist and reservations -----------------------------------
# A waiting party is a Restaurant Booking with no table and status Waitlisted;
# seating one assigns the table and flips it to Open.

def _company():
    # A site with no global default still has a Company; the old bare-name
    # fallback was a NameError waiting for the first tenant that skipped it.
    return (frappe.defaults.get_global_default("company")
            or frappe.db.get_value("Company", {}, "name"))


def _waited_minutes(since):
    if not since:
        return 0
    return int((frappe.utils.now_datetime() - frappe.utils.get_datetime(since)).total_seconds() // 60)


def _booking_row(b):
    return {
        "name": b.name,
        "guest": frappe.db.get_value("Customer", b.customer, "customer_name") or b.customer or "Guest",
        "covers": b.no_of_people or 0,
        "contact": b.contact_number or "",
        "status": b.status,
        "table": b.table,
        "table_label": frappe.db.get_value("Restaurant Object", b.table, "description") if b.table else "",
        "at": str(b.reservation_time or ""),
        "waited": _waited_minutes(b.creation),
    }


@frappe.whitelist()
def waitlist():
    """Parties waiting at the door, longest wait first."""
    rows = frappe.get_all(
        "Restaurant Booking",
        filters={"status": "Waitlisted"},
        fields=["name", "customer", "no_of_people", "contact_number", "status", "table",
                "reservation_time", "creation"],
        order_by="creation asc",
    )
    return [_booking_row(frappe._dict(r)) for r in rows]


@frappe.whitelist()
def add_to_waitlist(guest_name, covers=2, contact=None):
    """Put a walk-in on the queue without holding a table."""
    guest_name = (guest_name or "").strip()
    if not guest_name:
        frappe.throw(frappe._("A guest name is required"))

    now = frappe.utils.now_datetime()
    booking = frappe.get_doc({
        "doctype": "Restaurant Booking",
        "customer": _walkin_customer(guest_name, contact),
        "contact_number": contact,
        "no_of_people": int(covers or 1),
        "reservation_time": now,
        "reservation_end_time": frappe.utils.add_to_date(now, hours=2),
        "status": "Waitlisted",
        "company": _company(),
    })
    booking.insert(ignore_permissions=True)
    frappe.db.commit()
    return _booking_row(booking)


@frappe.whitelist()
def book_table(guest_name, covers=2, when=None, contact=None, table=None):
    """Take a reservation for later. No table is held: it is chosen on arrival,
    which is how a floor actually works — the right table depends on the night."""
    guest_name = (guest_name or "").strip()
    if not guest_name:
        frappe.throw(frappe._("A guest name is required"))
    when = frappe.utils.get_datetime(when) if when else frappe.utils.now_datetime()
    if table:
        _seats_or_throw(table, covers)

    booking = frappe.get_doc({
        "doctype": "Restaurant Booking",
        "customer": _walkin_customer(guest_name, contact),
        "contact_number": contact,
        "no_of_people": int(covers or 2),
        "reservation_time": when,
        "reservation_end_time": frappe.utils.add_to_date(when, hours=2),
        "table": table,
        "status": "Open",
        "company": _company(),
    })
    booking.insert(ignore_permissions=True)
    frappe.db.commit()
    return _booking_row(booking)


@frappe.whitelist()
def seat_from_waitlist(booking, table, waiter=None):
    """Give a waiting party a table: the queue's whole purpose."""
    doc = frappe.get_doc("Restaurant Booking", booking)
    obj = frappe.db.get_value("Restaurant Object", table, ["name", "room", "company"], as_dict=True)
    if not obj:
        frappe.throw(frappe._("Unknown table"))
    _seats_or_throw(obj.name, doc.no_of_people)

    now = frappe.utils.now_datetime()
    doc.table = obj.name
    doc.status = "Open"
    # reservation_time stays the time they arrived or were promised — overwriting it
    # would make both the wait and a late reservation unmeasurable.
    doc.seated_at = now
    doc.reservation_end_time = frappe.utils.add_to_date(now, hours=2)
    if waiter and frappe.db.has_column("Restaurant Booking", "waiter"):
        doc.waiter = waiter
    doc.save(ignore_permissions=True)

    frappe.db.set_value("Restaurant Object", obj.name, "customer", doc.customer)
    frappe.db.commit()

    return {"booking": doc.name, "table": obj.name, "room": obj.room,
            "order": _open_check(doc, obj), "waited": _waited_minutes(doc.creation)}


@frappe.whitelist()
def close_booking(booking, status="No Show"):
    """Mark a party as a no-show, or as having left before being seated."""
    if status not in ("No Show", "Cancelled"):
        frappe.throw(frappe._("Use No Show or Cancelled"))
    frappe.db.set_value("Restaurant Booking", booking, "status", status)
    frappe.db.commit()
    return {"booking": booking, "status": status}


@frappe.whitelist()
def reservations(day=None):
    """Bookings for a day, so the host can see who is expected."""
    day = day or frappe.utils.today()
    filters = {"reservation_time": ["between", [day + " 00:00:00", day + " 23:59:59"]],
               "status": ["!=", "Waitlisted"]}
    # A party already sitting down is on the floor, not at the door.
    if frappe.db.has_column("Restaurant Booking", "seated_at"):
        filters["seated_at"] = ["is", "not set"]
    rows = frappe.get_all(
        "Restaurant Booking",
        filters=filters,
        fields=["name", "customer", "no_of_people", "contact_number", "status", "table",
                "reservation_time", "creation"],
        order_by="reservation_time asc",
    )
    return [_booking_row(frappe._dict(r)) for r in rows]


@frappe.whitelist()
def door_summary():
    """One call for the door button's badge and the panel's header."""
    waiting = waitlist()
    turns = turn_metrics()
    return {
        "waiting": len(waiting),
        "covers_waiting": sum(w["covers"] for w in waiting),
        "longest_wait": max([w["waited"] for w in waiting], default=0),
        "free_tables": len(free_tables()),
        "expected_today": len(reservations()),
        # the host quotes a wait off the average turn, so it belongs on the door
        "avg_turn": turns["avg_turn"],
        "turns_today": turns["turns"],
        "seated_now": turns["seated_now"],
    }


@frappe.whitelist()
def free_table(table, status="Success", booking=None):
    """Close the party whose check was paid, giving its seats back.

    On a shared table only that party leaves; closing every booking would evict
    the strangers sitting next to them.
    """
    now = frappe.utils.now_datetime()
    closed = []
    filters = {"table": table, "status": "Open"}
    if booking:
        filters = {"name": booking, "status": "Open"}
    for b in frappe.get_all("Restaurant Booking", filters=filters, fields=["name"]):
        frappe.db.set_value("Restaurant Booking", b.name,
                            {"status": status, "left_at": now}, update_modified=False)
        closed.append(b.name)
    # Nobody left sitting clears the tile — even when this call closed no booking:
    # a check paid on a bookingless table used to leave its guest's name behind.
    if not parties_at(table):
        frappe.db.set_value("Restaurant Object", table,
                            {"customer": None, "current_user": None}, update_modified=False)

    frappe.db.commit()
    return {"table": table, "closed": closed}


def _turn_rows(from_date=None, to_date=None):
    """One row per table: parties served, covers, and how long they sat."""
    from_date = from_date or frappe.utils.today()
    to_date = to_date or from_date
    # The stamps are custom fields; without them there are no turns to report,
    # and the door panel must not fail over a metric.
    if not frappe.db.has_column("Restaurant Booking", "seated_at"):
        return []

    bookings = frappe.db.sql(
        """
        select b.table as tbl, b.no_of_people as covers,
            coalesce(b.seated_at, b.reservation_time) as seated, b.left_at as left_at
        from `tabRestaurant Booking` b
        where b.left_at is not null
            and b.status = 'Success'
            and b.table is not null and b.table != ''
            and date(b.left_at) between %(from_date)s and %(to_date)s
        """,
        {"from_date": from_date, "to_date": to_date},
        as_dict=True,
    )

    tables = {t.name: t for t in frappe.get_all(
        "Restaurant Object", filters={"type": "Table"},
        fields=["name", "description", "room", "no_of_seats"])}

    by_table = {}
    for b in bookings:
        if not b.seated or not b.left_at:
            continue
        minutes = int((frappe.utils.get_datetime(b.left_at)
                       - frappe.utils.get_datetime(b.seated)).total_seconds() // 60)
        # A clock that runs backwards, or a party parked overnight, is bad data
        # rather than a turn — counting it would poison the average.
        if minutes < 0 or minutes > 12 * 60:
            continue
        row = by_table.setdefault(b.tbl, {"turns": 0, "covers": 0, "minutes": []})
        row["turns"] += 1
        row["covers"] += int(b.covers or 0)
        row["minutes"].append(minutes)

    out = []
    for name, agg in by_table.items():
        t = tables.get(name) or frappe._dict()
        seats = t.get("no_of_seats") or 0
        mins = agg["minutes"]
        out.append({
            "table": name,
            "table_label": t.get("description") or name,
            "room": t.get("room") or "",
            "seats": seats,
            "turns": agg["turns"],
            "covers": agg["covers"],
            "avg_turn": int(sum(mins) / len(mins)) if mins else 0,
            "longest_turn": max(mins) if mins else 0,
            "turns_per_seat": round(agg["turns"] / seats, 2) if seats else 0,
        })
    out.sort(key=lambda r: (-r["turns"], r["table_label"]))
    return out


@frappe.whitelist()
def turn_metrics(day=None):
    """How the floor performed: turns, covers and average sitting time."""
    rows = _turn_rows(day, day)
    all_minutes = [r["avg_turn"] for r in rows for _ in range(r["turns"])]
    turns = sum(r["turns"] for r in rows)
    seated_now = frappe.db.count("Restaurant Booking", {"status": "Open", "table": ["!=", ""]})
    total_tables = frappe.db.count("Restaurant Object", {"type": "Table"})
    return {
        "day": day or frappe.utils.today(),
        "turns": turns,
        "covers": sum(r["covers"] for r in rows),
        "avg_turn": int(sum(all_minutes) / len(all_minutes)) if all_minutes else 0,
        "longest_turn": max([r["longest_turn"] for r in rows], default=0),
        "tables_used": len(rows),
        "total_tables": total_tables,
        "seated_now": seated_now,
        "turns_per_table": round(turns / total_tables, 2) if total_tables else 0,
        "tables": rows,
    }


# ---- staff: the floor's PIN pad doubles as the shift clock ------------------
# Employee is erpnext and always present; Employee Checkin is hrms, so every use
# of it is guarded and a floor without hrms still signs waiters in.


def _has_hrms():
    return "hrms" in frappe.get_installed_apps()


def _last_log(employee):
    rows = frappe.get_all(
        "Employee Checkin",
        filters={"employee": employee, "time": [">=", frappe.utils.today() + " 00:00:00"]},
        fields=["name", "log_type", "time"],
        # Employee Checkin.time keeps only seconds, so two logs can tie —
        # creation breaks it, otherwise the order is whatever the db returns.
        order_by="time desc, creation desc",
        limit=1,
    )
    return rows[0] if rows else None


def _log_checkin(waiter, log_type):
    """Record a floor sign-in as attendance. Never fatal: a waiter must be able
    to start serving even if HR bookkeeping fails."""
    if not _has_hrms():
        return None
    employee = frappe.db.get_value("Restaurant Waiter", waiter, "employee")
    if not employee:
        return None
    try:
        last = _last_log(employee)
        if last and last["log_type"] == log_type:
            return last["name"]
        doc = frappe.get_doc({
            "doctype": "Employee Checkin",
            "employee": employee,
            "log_type": log_type,
            "time": frappe.utils.now_datetime(),
            "device_id": "POS",
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return doc.name
    except Exception:
        frappe.log_error(title="waiter checkin")
        return None


@frappe.whitelist()
def waiter_sign_out(waiter, pin=None, token=None):
    """Sign a waiter off the terminal and close their attendance for the shift."""
    row = _authorised(waiter, pin, token)
    frappe.cache().delete_value(_token_key(waiter))
    return {"waiter": row.name, "waiter_name": row.waiter_name,
            "checkin": _log_checkin(waiter, "OUT")}


@frappe.whitelist()
def staff():
    """The roster a manager needs: who is on, who they are in HR, tables held."""
    held = {}
    for r in frappe.get_all("Restaurant Object", filters={"type": "Table"}, fields=["name", "waiter"]):
        if r.waiter:
            held[r.waiter] = held.get(r.waiter, 0) + 1

    out = []
    for w in frappe.get_all(
        "Restaurant Waiter",
        fields=["name", "waiter_name", "active", "colour", "employee", "user"],
        order_by="waiter_name",
    ):
        row = {
            "waiter": w.name,
            "waiter_name": w.waiter_name,
            "initials": _initials(w.waiter_name),
            "active": bool(w.active),
            "colour": w.colour,
            "employee": w.employee,
            "user": w.user,
            "tables": held.get(w.name, 0),
            "designation": "",
            "on_shift": False,
            "since": "",
        }
        if w.employee:
            row["designation"] = frappe.db.get_value("Employee", w.employee, "designation") or ""
            if _has_hrms():
                last = _last_log(w.employee)
                row["on_shift"] = bool(last and last["log_type"] == "IN")
                row["since"] = str(last["time"]) if last else ""
        out.append(row)
    return out


@frappe.whitelist()
def link_employee(waiter, employee):
    """Point a waiter at their HR record so the PIN pad can clock them in."""
    if not frappe.db.exists("Employee", employee):
        frappe.throw(frappe._("Unknown employee"))
    frappe.db.set_value("Restaurant Waiter", waiter, "employee", employee)
    frappe.db.commit()
    return {"waiter": waiter, "employee": employee}


# ---- deleting a table ------------------------------------------------------
# An unpaid check keeps its table linked for good and blocks the delete; it can
# be closed. An invoiced one is history and must not be.

OPEN_ORDER_STATES = ["not in", ["Invoiced", "Cancelled"]]


@frappe.whitelist()
def table_blockers(table):
    """What is stopping this table from being deleted, in plain terms."""
    obj = frappe.db.get_value("Restaurant Object", table, ["name", "description"], as_dict=True)
    if not obj:
        frappe.throw(frappe._("That table no longer exists"))

    open_orders = frappe.get_all(
        "Table Order", filters={"table": table, "status": OPEN_ORDER_STATES},
        fields=["name", "status", "amount"], order_by="creation")
    invoiced = frappe.get_all(
        "Table Order", filters={"table": table, "status": "Invoiced"}, fields=["name"])
    bookings = frappe.get_all(
        "Restaurant Booking", filters={"table": table, "status": "Open"}, fields=["name"])

    return {
        "table": table,
        "label": obj.description or table,
        "open_orders": open_orders,
        "invoiced_orders": len(invoiced),
        "open_bookings": len(bookings),
        # Invoiced orders are the books; the table has to stay for them to make sense.
        "deletable": not invoiced,
    }


@frappe.whitelist()
def release_table(table):
    """Close the unpaid checks and seatings holding a table. Never touches an
    invoiced order — that is a sale, and the table is part of its record."""
    # Voiding checks hides sales, so it belongs to whoever can bank the day —
    # a waiter must not order, pocket cash, and release the evidence.
    if not frappe.has_permission("POS Closing Entry", ptype="create"):
        frappe.throw(frappe._("Releasing a table is the cashier's or manager's job."),
                     frappe.PermissionError)
    closed_orders, closed_bookings = [], []

    for o in frappe.get_all("Table Order", filters={"table": table, "status": OPEN_ORDER_STATES},
                            fields=["name", "docstatus"]):
        doc = frappe.get_doc("Table Order", o.name)
        if doc.docstatus == 1:
            doc.cancel()
        frappe.delete_doc("Table Order", o.name, force=1, ignore_permissions=True)
        closed_orders.append(o.name)

    now = frappe.utils.now_datetime()
    for b in frappe.get_all("Restaurant Booking", filters={"table": table, "status": "Open"},
                            fields=["name"]):
        values = {"status": "Cancelled"}
        if frappe.db.has_column("Restaurant Booking", "left_at"):
            values["left_at"] = now
        frappe.db.set_value("Restaurant Booking", b.name, values, update_modified=False)
        closed_bookings.append(b.name)

    frappe.db.set_value("Restaurant Object", table,
                        {"customer": None, "current_user": None, "waiter": None},
                        update_modified=False)
    frappe.db.commit()

    # Tell every open floor the tile changed, or the old badge waits for a reload.
    try:
        frappe.get_doc("Restaurant Object", table)._on_update()
    except Exception:
        frappe.log_error(title="release_table synchronize")

    return {"table": table, "orders": closed_orders, "bookings": closed_bookings}


# ---- closing the day -------------------------------------------------------
# A shift left open bills into yesterday and then refuses today's sales with
# "POS Opening Entry is outdated", which reads as a broken till.


def _open_shift_doc(pos_profile=None):
    filters = {"status": "Open", "docstatus": 1}
    if pos_profile:
        filters["pos_profile"] = pos_profile
    name = frappe.db.get_value("POS Opening Entry", filters, "name", order_by="period_start_date desc")
    return frappe.get_doc("POS Opening Entry", name) if name else None


@frappe.whitelist()
def day_summary(pos_profile=None):
    """What closing would sweep up, so nobody closes a day blind."""
    shift = _open_shift_doc(pos_profile)
    if not shift:
        return {"open": False}

    invoices = frappe.get_all(
        "POS Invoice",
        filters={"docstatus": 1, "pos_profile": shift.pos_profile,
                 "posting_date": [">=", frappe.utils.getdate(shift.period_start_date)]},
        fields=["name", "grand_total", "customer"])
    open_orders = frappe.get_all(
        "Table Order",
        filters={"status": ["not in", ["Invoiced", "Cancelled"]], "show_in_pos": 1},
        fields=["name", "table", "amount"])

    return {
        "open": True,
        "shift": shift.name,
        "profile": shift.pos_profile,
        "opened_at": str(shift.period_start_date),
        "stale": frappe.utils.getdate(shift.period_start_date) < frappe.utils.getdate(),
        "invoices": len(invoices),
        "sales": round(sum(i.grand_total or 0 for i in invoices), 2),
        "open_checks": len(open_orders),
        "open_checks_value": round(sum(o.amount or 0 for o in open_orders), 2),
        "currency": frappe.db.get_value("Company", shift.company, "default_currency"),
    }


@frappe.whitelist()
def close_day(pos_profile=None, force=0):
    """Close the selling day: bank the shift so tomorrow can open a fresh one.

    Refuses while checks are still open unless told otherwise — those tables
    would be stranded on a closed shift with no way to bill them.
    """
    from erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry import (
        make_closing_entry_from_opening,
    )

    if not frappe.has_permission("POS Closing Entry", ptype="create"):
        frappe.throw(frappe._("Closing the day is the cashier's or manager's job."),
                     frappe.PermissionError)

    shift = _open_shift_doc(pos_profile)
    if not shift:
        return {"closed": None, "message": frappe._("The counter is already closed")}

    summary = day_summary(pos_profile)
    if summary["open_checks"] and not int(force or 0):
        frappe.throw(frappe._("{0} check(s) are still open. Settle them first, or close anyway.")
                     .format(summary["open_checks"]))

    closing = make_closing_entry_from_opening(shift)
    closing.posting_date = frappe.utils.today()
    closing.posting_time = frappe.utils.nowtime()
    closing.period_end_date = frappe.utils.now_datetime()
    closing.insert(ignore_permissions=True)
    closing.submit()
    frappe.db.commit()

    swept = _end_of_day_sweep()

    return {"closed": closing.name, "shift": shift.name,
            "invoices": summary["invoices"], "sales": summary["sales"],
            "open_checks_left": summary["open_checks"],
            "parties_closed": len(swept["parties_closed"]),
            "sections_cleared": len(swept["sections_cleared"])}


# ---- seats, not tables ------------------------------------------------------
# Two parties can share a six-top: occupancy is counted in seats, and a party is
# one Restaurant Booking carrying its own waiter.


def _party_fields():
    fields = ["name", "customer", "no_of_people", "reservation_time", "creation"]
    for optional in ("waiter", "seated_at"):
        if frappe.db.has_column("Restaurant Booking", optional):
            fields.append(optional)
    return fields


def parties_at(table):
    """Every party still sitting at a table, oldest first.

    Not time-boxed: seats are held until the check is paid or the party is
    released, because a two-hour window would offer occupied chairs.
    """
    rows = frappe.get_all(
        "Restaurant Booking",
        filters={"table": table, "status": "Open"},
        fields=_party_fields(),
        order_by="creation asc",
    )
    return [frappe._dict(r) for r in rows]


def _party_row(p, orders=None):
    waiter = p.get("waiter")
    row = {
        "booking": p.name,
        "guest": frappe.db.get_value("Customer", p.customer, "customer_name") or p.customer or "Guest",
        "customer": p.customer,
        "covers": int(p.no_of_people or 0),
        "waiter": waiter,
        "initials": _initials(waiter) if waiter else "",
        "colour": (frappe.db.get_value("Restaurant Waiter", waiter, "colour") or "#4b5563") if waiter else "#4b5563",
        "seated_at": str(p.get("seated_at") or p.get("reservation_time") or ""),
        "minutes": _waited_minutes(p.get("seated_at") or p.get("reservation_time")),
    }
    row["order"] = (orders or {}).get(p.name)
    return row


def _orders_by_booking(table):
    if not frappe.db.has_column("Table Order", "booking"):
        return {}
    return {
        o.booking: o.name
        for o in frappe.get_all(
            "Table Order",
            filters={"table": table, "booking": ["is", "set"],
                     "status": ["not in", ["Cancelled", "Invoiced"]]},
            fields=["name", "booking"],
        )
    }


def table_seats(table, doc=None):
    """capacity / occupied / free for one table, with the parties on it."""
    t = doc or frappe.db.get_value(
        "Restaurant Object", table,
        ["name", "description", "room", "company", "no_of_seats"], as_dict=True)
    if not t:
        frappe.throw(frappe._("Unknown table"))

    parties = parties_at(t.name)
    orders = _orders_by_booking(t.name)
    capacity = int(t.get("no_of_seats") or 0)
    occupied = sum(int(p.no_of_people or 0) for p in parties)
    rows = [_party_row(p, orders) for p in parties]

    # A check opened straight on the pad has unknown covers: take the whole table.
    if not parties and _table_busy(t.name, t.get("company")):
        occupied = capacity
        rows = [{"booking": None, "guest": frappe._("Open check"), "customer": None,
                 "covers": 0, "waiter": frappe.db.get_value("Restaurant Object", t.name, "waiter"),
                 "initials": "", "colour": "#4b5563", "seated_at": "", "minutes": 0,
                 "order": None, "unseated": True}]

    return {
        "table": t.name,
        "description": t.get("description") or t.name,
        "room": t.get("room"),
        "capacity": capacity,
        "occupied": occupied,
        # Unrecorded capacity reads as unknown, not as full.
        "free": max(capacity - occupied, 0) if capacity else None,
        "parties": rows,
    }


@frappe.whitelist()
def table_occupancy(room=None):
    """Seat counts for the whole floor, keyed by table — one call per repaint.

    Deliberately bulk: per-table lookups meant forty-odd queries a repaint, and
    the floor polls this, so it showed up as a slow floor.
    """
    filters = {"type": "Table"}
    if room:
        filters["room"] = room

    tables = frappe.get_all(
        "Restaurant Object", filters=filters,
        fields=["name", "description", "room", "company", "no_of_seats", "waiter"])
    if not tables:
        return {}

    names = [t.name for t in tables]
    parties = frappe.get_all(
        "Restaurant Booking",
        filters={"table": ["in", names], "status": "Open"},
        fields=_party_fields() + ["table"],
        order_by="creation asc",
    )

    # A fresh check sits in status "Opened": it must link to its party, but it
    # does not make a table busy — that matches the app's own orders_count.
    orders = frappe.get_all(
        "Table Order",
        filters={"table": ["in", names], "show_in_pos": 1,
                 "status": ["not in", ["Cancelled", "Invoiced"]]},
        fields=["name", "table", "status"] + (["booking"] if frappe.db.has_column("Table Order", "booking") else []),
    )

    customers = {c.name: c.customer_name for c in frappe.get_all(
        "Customer", filters={"name": ["in", list({p.customer for p in parties if p.customer})] or [""]},
        fields=["name", "customer_name"])}
    colours = {w.name: w.colour for w in frappe.get_all("Restaurant Waiter", fields=["name", "colour"])}

    by_table = {}
    for p in parties:
        by_table.setdefault(p.table, []).append(p)
    orders_by_booking, busy = {}, set()
    for o in orders:
        if o.status != "Opened":
            busy.add(o.table)
        if o.get("booking"):
            orders_by_booking[o.booking] = o.name

    out = {}
    for t in tables:
        rows = []
        capacity = int(t.get("no_of_seats") or 0)
        occupied = 0
        for p in by_table.get(t.name, []):
            occupied += int(p.no_of_people or 0)
            waiter = p.get("waiter")
            rows.append({
                "booking": p.name,
                "guest": customers.get(p.customer) or p.customer or "Guest",
                "customer": p.customer,
                "covers": int(p.no_of_people or 0),
                "waiter": waiter,
                "initials": _initials(waiter) if waiter else "",
                "colour": (colours.get(waiter) or "#4b5563") if waiter else "#4b5563",
                "seated_at": str(p.get("seated_at") or p.get("reservation_time") or ""),
                "minutes": _waited_minutes(p.get("seated_at") or p.get("reservation_time")),
                "order": orders_by_booking.get(p.name),
            })

        if not rows and t.name in busy:
            occupied = capacity
            rows = [{"booking": None, "guest": frappe._("Open check"), "customer": None,
                     "covers": 0, "waiter": t.get("waiter"), "initials": "", "colour": "#4b5563",
                     "seated_at": "", "minutes": 0, "order": None, "unseated": True}]

        out[t.name] = {
            "table": t.name,
            "description": t.get("description") or t.name,
            "room": t.get("room"),
            "capacity": capacity,
            "occupied": occupied,
            "free": max(capacity - occupied, 0) if capacity else None,
            "parties": rows,
        }
    return out


def free_seats(table):
    """Seats a party could still be put on. None when capacity is unrecorded."""
    return table_seats(table)["free"]


def _seats_or_throw(table, covers):
    """Refuse a party that does not fit in what is left of the table."""
    seats = table_seats(table)
    covers = int(covers or 0)
    if seats["free"] is None:
        return seats
    if covers > seats["free"]:
        if seats["occupied"]:
            frappe.throw(frappe._("{0} has {1} of {2} seats free — {3} won't fit.").format(
                seats["description"], seats["free"], seats["capacity"], covers))
        frappe.throw(frappe._("{0} seats {1}, not {2}.").format(
            seats["description"], seats["capacity"], covers))
    return seats


def _open_check(booking, table):
    """Open this party's own check, so a shared table bills as two."""
    try:
        order = frappe.get_doc("Restaurant Object", table.name).add_order()
    except Exception:
        # Seating must not fail because the pad refused a check.
        frappe.log_error(title="open check at seating")
        return None

    values = {"customer": booking.customer, "dinners": booking.no_of_people}
    if frappe.db.has_column("Table Order", "booking"):
        values["booking"] = booking.name
    if booking.get("waiter") and frappe.db.has_column("Table Order", "waiter"):
        values["waiter"] = booking.waiter

    frappe.db.set_value("Table Order", order.name, values, update_modified=False)
    frappe.db.commit()
    return order.name


@frappe.whitelist()
def parties(table):
    """The parties on one table, for the pad's 'whose check is this?' picker."""
    return table_seats(table)["parties"]


@frappe.whitelist()
def add_covers(booking, covers):
    """A party grew. Seats have to be there for the extra chairs."""
    doc = frappe.get_doc("Restaurant Booking", booking)
    extra = int(covers or 0)
    if extra <= 0:
        frappe.throw(frappe._("How many more guests?"))
    if doc.status != "Open":
        frappe.throw(frappe._("That party has already left"))

    seats = table_seats(doc.table)
    if seats["free"] is not None and extra > seats["free"]:
        frappe.throw(frappe._("Only {0} seat(s) free on {1}.").format(
            seats["free"], seats["description"]))

    doc.no_of_people = int(doc.no_of_people or 0) + extra
    doc.save(ignore_permissions=True)

    if frappe.db.has_column("Table Order", "booking"):
        for o in frappe.get_all("Table Order", filters={
                "booking": doc.name, "status": ["not in", ["Cancelled", "Invoiced"]]}):
            frappe.db.set_value("Table Order", o.name, "dinners", doc.no_of_people,
                                update_modified=False)
    frappe.db.commit()
    return table_seats(doc.table)


@frappe.whitelist()
def release_party(booking, status="Cancelled"):
    """Give a party's seats back without a sale — a walk-out, or a mis-seat."""
    doc = frappe.db.get_value("Restaurant Booking", booking, ["name", "table", "status"], as_dict=True)
    if not doc:
        frappe.throw(frappe._("Unknown party"))
    frappe.db.set_value("Restaurant Booking", booking,
                        {"status": status, "left_at": frappe.utils.now_datetime()},
                        update_modified=False)
    if doc.table and not parties_at(doc.table):
        frappe.db.set_value("Restaurant Object", doc.table,
                            {"customer": None, "current_user": None}, update_modified=False)
    frappe.db.commit()
    return table_seats(doc.table) if doc.table else {"table": None}


@frappe.whitelist()
def ticket_order(identifier):
    """The Table Order behind one kitchen-board item, for printing its ticket."""
    parent = frappe.db.get_value("Order Entry Item", {"identifier": identifier}, "parent")
    if not parent:
        frappe.throw(frappe._("That ticket no longer exists"))
    return parent


@frappe.whitelist()
def claim_party(booking, waiter, pin=None, token=None):
    """Give one party to a waiter. A shared table has one owner per party."""
    row = _authorised(waiter, pin, token)
    if not house_shift():
        frappe.throw(frappe._("The counter is closed. Open the day first."))
    doc = frappe.db.get_value("Restaurant Booking", booking, ["name", "table", "status"], as_dict=True)
    if not doc:
        frappe.throw(frappe._("Unknown party"))
    if doc.status != "Open":
        frappe.throw(frappe._("That party has already left"))

    frappe.db.set_value("Restaurant Booking", booking, "waiter", waiter, update_modified=False)
    if frappe.db.has_column("Table Order", "booking"):
        for o in frappe.get_all("Table Order", filters={
                "booking": booking, "status": ["not in", ["Cancelled", "Invoiced"]]}):
            frappe.db.set_value("Table Order", o.name, "waiter", waiter, update_modified=False)
    frappe.db.commit()

    return {"booking": booking, "waiter": waiter, "waiter_name": row.waiter_name,
            "initials": _initials(row.waiter_name), "table": doc.table}


# ---- opening the day -------------------------------------------------------
# The pad used to fall through to erpnext's create_opening_voucher(), so the
# first waiter to ring a dish opened the drawer with a float nobody counted.


def _default_profile():
    company = _company()
    return (frappe.db.get_value("POS Profile", {"company": company, "disabled": 0}, "name")
            or frappe.db.get_value("POS Profile", {"disabled": 0}, "name"))


@frappe.whitelist()
def opening_floats(pos_profile=None):
    """The float rows a manager counts into the drawer before service."""
    profile = pos_profile or _default_profile()
    if not profile:
        frappe.throw(frappe._("No POS Profile is set up"))
    prof = frappe.get_doc("POS Profile", profile)
    return {
        "profile": prof.name,
        "company": prof.company,
        "currency": frappe.db.get_value("Company", prof.company, "default_currency"),
        "modes": [p.mode_of_payment for p in prof.payments] or ["Cash"],
    }


@frappe.whitelist()
def open_day(pos_profile=None, balances=None):
    """Open the selling day with a counted float. Manager's act, never automatic."""
    # The insert below bypasses roles, so the door is guarded here instead.
    if not frappe.has_permission("POS Opening Entry", ptype="create"):
        frappe.throw(frappe._("Opening the day is the cashier's or manager's job."),
                     frappe.PermissionError)
    profile = pos_profile or _default_profile()
    if not profile:
        frappe.throw(frappe._("No POS Profile is set up"))

    standing = _open_shift_doc(profile)
    if standing:
        if frappe.utils.getdate(standing.period_start_date) < frappe.utils.getdate():
            frappe.throw(frappe._("A shift from {0} is still open. Close the day first.").format(
                frappe.utils.formatdate(standing.period_start_date)))
        return {"opened": None, "shift": standing.name,
                "message": frappe._("The counter is already open")}

    if isinstance(balances, str):
        balances = frappe.parse_json(balances or "{}")
    balances = balances or {}

    prof = frappe.get_doc("POS Profile", profile)
    modes = [p.mode_of_payment for p in prof.payments] or ["Cash"]

    # A naming counter behind a surviving document collides on insert and the
    # day refuses to open; heal the series against what actually exists.
    for series in frappe.db.sql_list(
            "select name from tabSeries where name like 'POS-OPE%%'"):
        last = frappe.db.sql(
            "select max(cast(substring_index(name, '-', -1) as unsigned)) "
            "from `tabPOS Opening Entry` where name like %s", series + "%")[0][0] or 0
        frappe.db.sql("update tabSeries set current = greatest(current, %s) where name = %s",
                      (last, series))

    doc = frappe.get_doc({
        "doctype": "POS Opening Entry",
        "company": prof.company,
        "pos_profile": prof.name,
        "user": frappe.session.user,
        "period_start_date": frappe.utils.now_datetime(),
        "posting_date": frappe.utils.today(),
        "balance_details": [
            {"mode_of_payment": m, "opening_amount": frappe.utils.flt(balances.get(m) or 0)}
            for m in modes
        ],
    })
    doc.insert(ignore_permissions=True)
    doc.submit()
    frappe.db.commit()

    return {"opened": doc.name, "shift": doc.name, "profile": prof.name,
            "float": sum(frappe.utils.flt(balances.get(m) or 0) for m in modes),
            "currency": frappe.db.get_value("Company", prof.company, "default_currency")}


def _end_of_day_sweep():
    """Close what service left behind: sections and parties are shift-long.

    A badge left on a table outlives the shift that granted it, and a party
    still open once the shift is banked has no way to be billed.
    """
    now = frappe.utils.now_datetime()
    left = []
    for b in frappe.get_all("Restaurant Booking", filters={"status": "Open"}, fields=["name"]):
        frappe.db.set_value("Restaurant Booking", b.name,
                            {"status": "Success", "left_at": now}, update_modified=False)
        left.append(b.name)

    cleared = []
    if frappe.db.has_column("Restaurant Object", "waiter"):
        for t in frappe.get_all("Restaurant Object",
                                filters={"type": "Table", "waiter": ["is", "set"]}, fields=["name"]):
            frappe.db.set_value("Restaurant Object", t.name, "waiter", None, update_modified=False)
            cleared.append(t.name)

    frappe.db.commit()
    return {"parties_closed": left, "sections_cleared": cleared}
