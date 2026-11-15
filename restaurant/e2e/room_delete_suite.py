"""Deleting a room: a clean room goes in one go with everything standing in it;
a room with anything on record stays whole and says why. Test sites only — it
creates and deletes ZZ Test rooms."""
import frappe
from restaurant_management import house

PASSED = []
ROOM, T1, T2, PC = "ZZ Test Room", "ZZ Test T1", "ZZ Test T2", "ZZ Test Kitchen"


def ok(name, cond, detail=""):
	PASSED.append(bool(cond))
	print("%s  %s%s" % ("PASS" if cond else "FAIL", name, ("   [%s]" % detail) if detail else ""))


def _obj(description, type_, room=None, **extra):
	doc = frappe.get_doc(dict(doctype="Restaurant Object", type=type_, description=description, room=room, **extra))
	doc.insert(ignore_permissions=True)
	return doc.name


def _exists(*names):
	return [n for n in names if frappe.db.exists("Restaurant Object", n)]


def _refused(fn):
	try:
		fn()
	except (frappe.ValidationError, frappe.PermissionError) as e:  # frappe's PermissionError is no ValidationError
		frappe.local.message_log = []
		return type(e).__name__
	return None


def _clear():
	for kind in ("Production Center", "Table", "Room"):
		for name in frappe.get_all("Restaurant Object", pluck="name",
		                           filters={"type": kind, "description": ["like", "ZZ Test%"]}):
			frappe.delete_doc("Restaurant Object", name, force=1, ignore_permissions=True)
	frappe.db.commit()


def _build():
	_obj(ROOM, "Room")
	_obj(T1, "Table", ROOM, no_of_seats=4)
	_obj(T2, "Table", ROOM, no_of_seats=2)
	# a kitchen screen in the room that takes orders only from T1: it links T1,
	# so the delete has to take it before the tables
	_obj(PC, "Production Center", ROOM, restricted_to_tables=1, restricted_tables=[{"origin": T1}])
	frappe.db.commit()


def run():
	frappe.set_user("Administrator")
	_clear()

	# --- a clean room goes, with everything in it -----------------------------
	_build()
	b = house.room_blockers(ROOM)
	ok("a clean room has nothing holding it", not b["reasons"], b["reasons"])
	ok("it names everything that goes with it", {o["name"] for o in b["contents"]} == {T1, T2, PC},
	   [o["name"] for o in b["contents"]])
	ok("the screen restricted to a table goes before the tables", b["contents"][0]["name"] == PC,
	   [o["name"] for o in b["contents"]])
	out = house.delete_room(ROOM)
	frappe.db.commit()
	ok("delete_room reports what it took", set(out["deleted"]) == {T1, T2, PC}, out)
	ok("the room and everything in it are gone", not _exists(ROOM, T1, T2, PC), _exists(ROOM, T1, T2, PC))

	# --- the delivery room stays ----------------------------------------------
	dr = frappe.db.get_single_value("Restaurant Settings", "delivery_room")
	if dr:
		before = frappe.db.count("Restaurant Object", {"room": dr})
		b = house.room_blockers(dr)
		ok("the delivery room says why it stays", any("delivery room" in r for r in b["reasons"]), b["reasons"])
		ok("and deleting it is refused", _refused(lambda: house.delete_room(dr)))
		ok("with nothing taken", _exists(dr) and frappe.db.count("Restaurant Object", {"room": dr}) == before)
	else:
		print("SKIP  no delivery room on this site")

	# --- a room with sales on record stays, whole ------------------------------
	sold = frappe.db.get_value("Table Order", {"room": ["is", "set"], "status": "Invoiced"}, "room")
	if sold and frappe.db.exists("Restaurant Object", sold):
		tables = frappe.get_all("Restaurant Object", filters={"room": sold}, pluck="name")
		b = house.room_blockers(sold)
		ok("a room with sales says its checks keep it", any("check(s) on record" in r for r in b["reasons"]), b["reasons"])
		ok("and deleting it is refused", _refused(lambda: house.delete_room(sold)))
		frappe.db.rollback()
		ok("with the room and every table still there", len(_exists(sold, *tables)) == len(tables) + 1,
		   "%d of %d" % (len(_exists(sold, *tables)), len(tables) + 1))
	else:
		print("SKIP  no invoiced check on this site (SIMULATE=1 seeds some)")

	# --- only someone who may delete floor objects can ---------------------------
	_build()
	user = "zz-room-test@example.com"
	if not frappe.db.exists("User", user):
		frappe.get_doc(dict(doctype="User", email=user, first_name="ZZ Room Test", send_welcome_email=0,
		                    roles=[{"role": "Restaurant User"}])).insert(ignore_permissions=True)
		frappe.db.commit()
	frappe.set_user(user)
	ok("a Restaurant User is told it is a manager's job", _refused(lambda: house.room_blockers(ROOM)) == "PermissionError")
	ok("and cannot delete it directly either", _refused(lambda: house.delete_room(ROOM)) == "PermissionError")
	frappe.set_user("Administrator")
	frappe.db.rollback()
	ok("so the room is untouched", len(_exists(ROOM, T1, T2, PC)) == 4)

	_clear()
	frappe.delete_doc("User", user, force=1, ignore_permissions=True)
	frappe.db.commit()
	print("%d/%d passed" % (sum(PASSED), len(PASSED)))
	if not all(PASSED):
		raise AssertionError("room delete suite failed")
