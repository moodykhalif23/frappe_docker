"""The floor's whole opening state in one round trip, and one broken piece must not
take the screen down with it. Read-only: it fetches, it never writes."""
import json
import time

import frappe
from restaurant_management import house

PASSED = []

PIECES = ("shift", "day", "occupancy", "holders", "policy", "board_room", "build", "delivery")


def ok(name, cond, detail=""):
	PASSED.append(bool(cond))
	print("%s  %s%s" % ("PASS" if cond else "FAIL", name, ("   [%s]" % detail) if detail else ""))


def run():
	frappe.set_user("cashier@etham.co.ke")

	boot = house.floor_boot()
	ok("the boot call answers with every piece the floor paints from",
	   set(boot) == set(PIECES), json.dumps(sorted(boot)))

	# --- each piece must equal what the separate call would have returned ---
	ok("its occupancy matches table_occupancy",
	   boot["occupancy"] == house.table_occupancy(), "differs")
	ok("its waiter badges match floor_waiters", boot["holders"] == house.floor_waiters(), "differs")
	ok("its policy matches waiter_policy", boot["policy"] == house.waiter_policy(), "differs")
	ok("its board room matches board_room", boot["board_room"] == house.board_room(), "differs")
	ok("its build stamp matches asset_version", boot["build"] == house.asset_version(), "differs")
	ok("its delivery settings match delivery_room", boot["delivery"] == house.delivery_room(), "differs")
	shift = house.house_shift()
	ok("its shift matches house_shift", boot["shift"] == shift, "differs")
	ok("its day summary matches day_summary", boot["day"] == house.day_summary(), "differs")

	snap = house.floor_snapshot()
	ok("the refresh snapshot carries both halves the repaint needs",
	   set(snap) == {"occupancy", "holders"}, json.dumps(sorted(snap)))
	ok("and each half matches its own call",
	   snap["occupancy"] == house.table_occupancy() and snap["holders"] == house.floor_waiters())

	# --- one broken piece must not cost the whole screen ---
	real = house.board_room
	try:
		house.board_room = lambda: (_ for _ in ()).throw(RuntimeError("kaboom"))
		hurt = house.floor_boot()
		ok("a piece that throws comes back empty rather than failing the boot",
		   set(hurt) == set(PIECES) and hurt["board_room"] is None, json.dumps(sorted(hurt)))
		ok("and the rest of the screen still has its data",
		   hurt["occupancy"] is not None and hurt["holders"] is not None,
		   json.dumps({k: (v is not None) for k, v in hurt.items()}))
	finally:
		house.board_room = real

	# --- the point of it: fewer trips ---
	t0 = time.time()
	house.floor_boot()
	bundled = time.time() - t0
	t0 = time.time()
	for fn in (house.house_shift, house.day_summary, house.table_occupancy, house.floor_waiters,
			   house.waiter_policy, house.board_room, house.asset_version, house.delivery_room):
		fn()
	apart = time.time() - t0
	ok("one call does the work of eight, without doing more of it",
	   bundled <= apart * 1.6 + 0.05,
	   "bundled %dms vs %dms apart" % (round(bundled * 1000), round(apart * 1000)))

	ok("both are whitelisted for the floor to call",
	   house.floor_boot in frappe.whitelisted and house.floor_snapshot in frappe.whitelisted,
	   "boot=%s snapshot=%s" % (house.floor_boot in frappe.whitelisted,
								house.floor_snapshot in frappe.whitelisted))

	print("%d/%d passed" % (sum(PASSED), len(PASSED)))
	if not all(PASSED):
		raise AssertionError("floor boot suite failed")
