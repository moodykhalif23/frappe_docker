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
		"seated_at": now,
		"company": obj.company,
	})
	booking.insert(ignore_permissions=True)

	# The pad refuses to open an order until the table itself carries a customer
	# ("You must set a customer to this table"), so seating has to set it too.
	frappe.db.set_value("Restaurant Object", obj.name, "customer", booking.customer)
	frappe.db.commit()

	return {"booking": booking.name, "customer": booking.customer, "table": obj.name, "room": obj.room}


WAITER_FIELD = {"fieldname": "waiter", "fieldtype": "Link", "options": "Restaurant Waiter", "label": "Waiter"}
SEATED_FIELD = {"fieldname": "seated_at", "fieldtype": "Datetime", "label": "Seated At", "read_only": 1}
LEFT_FIELD = {"fieldname": "left_at", "fieldtype": "Datetime", "label": "Left At", "read_only": 1}


def ensure_custom_fields():
	"""Idempotent: hangs the waiter link on the table, its orders and its invoices."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields({
		"Restaurant Object": [dict(WAITER_FIELD, insert_after="current_user")],
		"Table Order": [dict(WAITER_FIELD, insert_after="customer")],
		"POS Invoice": [dict(WAITER_FIELD, insert_after="customer", read_only=1)],
		"Restaurant Booking": [
			dict(SEATED_FIELD, insert_after="reservation_end_time"),
			dict(LEFT_FIELD, insert_after="seated_at"),
		],
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
		"checkin": _log_checkin(row.name, "IN"),
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


# ---- the door: waitlist and reservations -----------------------------------
#
# A waiting party is a Restaurant Booking with no table and status Waitlisted;
# seating one just assigns the table and flips it to Open. The doctype already
# carries no_of_people, contact_number and a No Show status, so the queue is a
# view over data that already exists rather than a new store.

def _company():
    # A site with no global default still has a Company; falling back to a bare
    # name here was a NameError waiting for the first tenant that skipped it.
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
    if table and (_table_busy(table, frappe.db.get_value("Restaurant Object", table, "company"))
                  or _table_seated(table)):
        frappe.throw(frappe._("That table is taken"))

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
def seat_from_waitlist(booking, table):
    """Give a waiting party a table: the queue's whole purpose."""
    doc = frappe.get_doc("Restaurant Booking", booking)
    obj = frappe.db.get_value("Restaurant Object", table, ["name", "room", "company"], as_dict=True)
    if not obj:
        frappe.throw(frappe._("Unknown table"))
    if _table_busy(obj.name, obj.company) or _table_seated(obj.name):
        frappe.throw(frappe._("That table was just taken — pick another"))

    now = frappe.utils.now_datetime()
    doc.table = obj.name
    doc.status = "Open"
    # reservation_time stays the time they arrived or were promised — overwriting it
    # would make both the wait and a late reservation unmeasurable.
    doc.seated_at = now
    doc.reservation_end_time = frappe.utils.add_to_date(now, hours=2)
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"booking": doc.name, "table": obj.name, "room": obj.room,
            "waited": _waited_minutes(doc.creation)}


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
def free_table(table, status="Success"):
    """Close the party sitting at a table so the next one can be seated.

    Called when the check is paid; until this exists a table stays 'seated'
    until its two-hour window lapses.
    """
    now = frappe.utils.now_datetime()
    closed = []
    for b in frappe.get_all("Restaurant Booking", filters={"table": table, "status": "Open"},
                            fields=["name"]):
        frappe.db.set_value("Restaurant Booking", b.name,
                            {"status": status, "left_at": now}, update_modified=False)
        closed.append(b.name)
    if closed:
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
#
# Employee lives in erpnext and is always there; Employee Checkin and Attendance
# come from hrms, so every use of them is guarded — the fork still runs without it.


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
#
# Seating opens a Table Order, and an order that was never paid keeps its table
# linked for good: the floor refuses the delete with frappe's raw link error.
# An unpaid check can be closed; an invoiced one is history and must not be.

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

    frappe.db.set_value("Restaurant Object", table, "customer", None)
    frappe.db.commit()
    return {"table": table, "orders": closed_orders, "bookings": closed_bookings}
