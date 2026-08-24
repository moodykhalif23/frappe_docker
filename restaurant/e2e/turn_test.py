# Seat -> sit -> pay -> free, asserted end to end against the real doctypes.
# Run: docker cp it into the app, then in `bench console`:
#   exec(open(".../turn_test.py").read(), globals()); run()

import frappe
from frappe.utils import add_to_date, now_datetime

from restaurant_management import house

GUEST = "Turn Test Party"
QGUEST = "Turn Test Queue"
BGUEST = "Turn Test Booking"


def _cleanup():
	for guest in (GUEST, QGUEST, BGUEST):
		for c in frappe.get_all("Customer", filters={"customer_name": guest}, fields=["name"]):
			for b in frappe.get_all("Restaurant Booking", filters={"customer": c.name}, fields=["name"]):
				frappe.db.set_value("Restaurant Booking", b.name, "table", None)
				frappe.delete_doc("Restaurant Booking", b.name, force=1, ignore_permissions=True)
			frappe.delete_doc("Customer", c.name, force=1, ignore_permissions=True)
	frappe.db.commit()


def run():
	results = []

	def check(label, cond, detail=""):
		results.append((bool(cond), label, detail))

	_cleanup()
	house.ensure_custom_fields()

	# --- walk-in: seated, occupies a table, releases it on payment ---
	free_before = house.free_tables(2)
	check("a free table exists to test with", free_before, f"{len(free_before)} free")
	if not free_before:
		return _report(results)

	table = free_before[0]["name"]
	seat = house.seat_walkin(GUEST, 2, table)
	booking = seat["booking"]

	b = frappe.get_doc("Restaurant Booking", booking)
	check("seating stamps seated_at", b.get("seated_at"), str(b.get("seated_at")))
	check("seated table leaves the free list",
		table not in [t["name"] for t in house.free_tables()])

	# Backdate the seating so the turn has a measurable length.
	frappe.db.set_value("Restaurant Booking", booking, "seated_at",
		add_to_date(now_datetime(), minutes=-45), update_modified=False)
	frappe.db.commit()

	freed = house.free_table(table)
	check("paying closes the booking on that table", booking in freed["closed"], str(freed))

	b.reload()
	check("closed booking reads Success", b.status == "Success", b.status)
	check("closing stamps left_at", b.get("left_at"), str(b.get("left_at")))
	check("table returns to the free list",
		table in [t["name"] for t in house.free_tables()])

	m = house.turn_metrics()
	row = next((r for r in m["tables"] if r["table"] == table), None)
	check("the turn lands on the table's row", row, str(row))
	if row:
		check("turn length is the 45 minutes it sat", 44 <= row["avg_turn"] <= 46, row["avg_turn"])
		check("covers counted", row["covers"] >= 2, row["covers"])
	check("floor summary counts the turn", m["turns"] >= 1, m["turns"])
	check("door summary carries the average", house.door_summary().get("avg_turn") >= 44,
		house.door_summary().get("avg_turn"))

	from restaurant_management.restaurant_management.report.table_turns import table_turns
	cols, rows = table_turns.execute({"from_date": frappe.utils.today(), "to_date": frappe.utils.today()})
	check("the report renders its columns", [c["fieldname"] for c in cols][:2] == ["table_label", "room"])
	check("the report shows the turn", any(r["table"] == table for r in rows), f"{len(rows)} rows")

	# --- queue: arrival time survives seating ---
	q = house.add_to_waitlist(QGUEST, 2)
	qb = frappe.get_doc("Restaurant Booking", q["name"])
	arrived = qb.reservation_time
	check("a queued party holds no table", not qb.table)
	check("the queue lists it", q["name"] in [w["name"] for w in house.waitlist()])

	free_now = house.free_tables(2)
	if free_now:
		house.seat_from_waitlist(q["name"], free_now[0]["name"])
		qb.reload()
		check("seating off the queue keeps the arrival time",
			str(qb.reservation_time) == str(arrived), f"{arrived} -> {qb.reservation_time}")
		check("seating off the queue stamps seated_at", qb.get("seated_at"))
		check("it leaves the queue", q["name"] not in [w["name"] for w in house.waitlist()])
		house.free_table(free_now[0]["name"])

	# --- a booking holds no table until they arrive ---
	when = add_to_date(now_datetime(), hours=2)
	free_count = len(house.free_tables())
	bk = house.book_table(BGUEST, 3, when)
	check("a booking holds no table", not frappe.db.get_value("Restaurant Booking", bk["name"], "table"))
	check("booking frees nothing on the floor", len(house.free_tables()) == free_count,
		f"{free_count} -> {len(house.free_tables())}")
	check("it shows under today's expected",
		bk["name"] in [r["name"] for r in house.reservations()])
	check("it is not in the queue", bk["name"] not in [w["name"] for w in house.waitlist()])

	free_now = house.free_tables(3)
	if free_now:
		booked_at = frappe.db.get_value("Restaurant Booking", bk["name"], "reservation_time")
		house.seat_from_waitlist(bk["name"], free_now[0]["name"])
		check("seating a booking keeps the time it was booked for",
			str(frappe.db.get_value("Restaurant Booking", bk["name"], "reservation_time")) == str(booked_at),
			str(booked_at))
		check("seating a booking stamps seated_at",
			frappe.db.get_value("Restaurant Booking", bk["name"], "seated_at"))
		house.free_table(free_now[0]["name"])

	nb = house.book_table(BGUEST, 2, add_to_date(now_datetime(), hours=3))
	house.close_booking(nb["name"], "No Show")
	check("a no-show closes", frappe.db.get_value("Restaurant Booking", nb["name"], "status") == "No Show")

	_cleanup()
	return _report(results)


def _report(results):
	failed = [r for r in results if not r[0]]
	for ok, label, detail in results:
		print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f"   [{detail}]" if detail else ""))
	print(f"\n{len(results) - len(failed)}/{len(results)} passed")
	if failed:
		raise AssertionError(f"{len(failed)} turn checks failed")
	return "ok"
