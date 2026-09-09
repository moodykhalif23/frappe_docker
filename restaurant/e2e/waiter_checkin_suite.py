"""A waiter sign-in records attendance even with geolocation tracking on, which is how
live differs from a fresh site — but a real geofence still holds. Test sites only: it
toggles HR Settings and creates its own employee, cleaning both up after."""
import json
import frappe
from frappe.utils import add_days, today

from restaurant_management import house

PASSED = []
EMP_NAME = "ZZ Checkin Probe"
LOC_NAME = "ZZ Checkin Location"
SHIFT_NAME = "ZZ Checkin Shift"


def ok(name, cond, detail=""):
	PASSED.append(bool(cond))
	print("%s  %s%s" % ("PASS" if cond else "FAIL", name, ("   [%s]" % detail) if detail else ""))


def _cleanup():
	for w in frappe.get_all("Restaurant Waiter", filters={"waiter_name": EMP_NAME}, pluck="name"):
		frappe.delete_doc("Restaurant Waiter", w, force=1, ignore_permissions=True)
	for e in frappe.get_all("Employee", filters={"employee_name": EMP_NAME}, pluck="name"):
		for c in frappe.get_all("Employee Checkin", filters={"employee": e}, pluck="name"):
			frappe.delete_doc("Employee Checkin", c, force=1, ignore_permissions=True)
		for a in frappe.get_all("Shift Assignment", filters={"employee": e}, pluck="name"):
			doc = frappe.get_doc("Shift Assignment", a)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc("Shift Assignment", a, force=1, ignore_permissions=True)
		frappe.db.set_value("Employee", e, "status", "Left", update_modified=False)
		frappe.delete_doc("Employee", e, force=1, ignore_permissions=True)
	for dt, nm in (("Shift Location", LOC_NAME), ("Shift Type", SHIFT_NAME)):
		if frappe.db.exists(dt, nm):
			frappe.delete_doc(dt, nm, force=1, ignore_permissions=True)
	frappe.db.commit()


def _fixture():
	if not frappe.db.exists("Designation", "Waiter"):
		frappe.get_doc({"doctype": "Designation", "designation_name": "Waiter"}).insert(
			ignore_permissions=True)
	company = frappe.defaults.get_global_default("company") or frappe.get_all(
		"Company", limit=1)[0].name
	emp = frappe.get_doc({
		"doctype": "Employee", "employee_name": EMP_NAME, "first_name": "ZZ", "last_name": "Probe",
		"gender": frappe.get_all("Gender", limit=1)[0].name,
		"date_of_birth": add_days(today(), -365 * 25), "date_of_joining": add_days(today(), -30),
		"company": company, "designation": "Waiter", "status": "Active",
	})
	emp.insert(ignore_permissions=True)
	waiter = frappe.get_doc({"doctype": "Restaurant Waiter", "waiter_name": EMP_NAME,
							 "employee": emp.name, "pin": "4931"})
	waiter.flags.ignore_permissions = True
	waiter.insert(ignore_permissions=True)
	frappe.db.commit()
	return emp.name, waiter.name


def _geofence(emp):
	"""A real shift location the employee is assigned to, so the geofence can be tested."""
	if not frappe.db.exists("Shift Location", LOC_NAME):
		frappe.get_doc({"doctype": "Shift Location", "location_name": LOC_NAME,
						"latitude": 0.1, "longitude": 0.1, "checkin_radius": 50}).insert(
			ignore_permissions=True)
	frappe.db.set_value("Shift Location", LOC_NAME,
						{"latitude": 0.1, "longitude": 0.1, "checkin_radius": 50},
						update_modified=False)
	if not frappe.db.exists("Shift Type", SHIFT_NAME):
		frappe.get_doc({"doctype": "Shift Type", "name": SHIFT_NAME,
						"start_time": "08:00:00", "end_time": "23:00:00"}).insert(
			ignore_permissions=True)
	a = frappe.get_doc({"doctype": "Shift Assignment", "employee": emp, "shift_type": SHIFT_NAME,
						"status": "Active", "start_date": add_days(today(), -1),
						"shift_location": LOC_NAME,
						"company": frappe.db.get_value("Employee", emp, "company")})
	a.flags.ignore_permissions = True
	a.insert(ignore_permissions=True)
	a.submit()
	frappe.db.commit()
	return LOC_NAME, SHIFT_NAME


_TICK = [0]


def _refused(emp, lat=None, lon=None):
	"""What hrms says about this check-in. Validated, never inserted."""
	# a distinct second per probe, or hrms's duplicate-log check answers instead
	_TICK[0] += 1
	when = frappe.utils.add_to_date(frappe.utils.now_datetime(), seconds=-61 * _TICK[0])
	doc = frappe.get_doc({"doctype": "Employee Checkin", "employee": emp, "log_type": "IN",
						  "time": when, "device_id": "POS",
						  "latitude": lat, "longitude": lon})
	try:
		doc.run_method("before_validate")
		doc.run_method("validate")
		return ""
	except Exception as e:
		return str(e) or e.__class__.__name__


def run():
	frappe.set_user("Administrator")
	ok("hrms is installed", house._has_hrms(), str(frappe.get_installed_apps()))
	if not house._has_hrms():
		print("%d/%d passed" % (sum(PASSED), len(PASSED)))
		return

	_cleanup()
	emp, waiter = _fixture()
	was = frappe.db.get_single_value("HR Settings", "allow_geolocation_tracking")
	try:
		# live runs with this on, a fresh site with it off: that is why live alone broke
		frappe.db.set_single_value("HR Settings", "allow_geolocation_tracking", 1)
		frappe.db.commit()
		frappe.clear_cache()
		msg = _refused(emp)
		ok("geolocation tracking on, no shift location: the sign-in is still accepted",
		   not msg, msg[:130])

		before = frappe.db.count("Employee Checkin", {"employee": emp})
		logged = house._log_checkin(waiter, "IN")
		frappe.db.commit()
		ok("and the attendance row is actually written",
		   bool(logged) and frappe.db.count("Employee Checkin", {"employee": emp}) > before,
		   "logged=%s" % logged)
		if logged:
			row = frappe.db.get_value("Employee Checkin", logged,
									  ["employee", "log_type", "device_id"], as_dict=True)
			ok("stamped as a POS sign-in for that employee",
			   row.employee == emp and row.log_type == "IN" and row.device_id == "POS",
			   json.dumps(row, default=str))

		loc, shift = _geofence(emp)
		near = _refused(emp)
		ok("but with a shift location assigned, coordinates are required again",
		   "atitude and longitude" in near, near[:130] or "it was accepted")
		far = _refused(emp, lat=40.0, lon=40.0)
		ok("and a sign-in outside the radius is still refused",
		   ("within" in far and "meters" in far) or "Radius" in far,
		   far[:130] or "it was accepted")
		inside = _refused(emp, lat=0.1, lon=0.1)
		ok("while a sign-in at the shift location goes through", not inside, inside[:130])
	finally:
		frappe.db.set_single_value("HR Settings", "allow_geolocation_tracking", was or 0)
		frappe.db.commit()
		frappe.clear_cache()
		_cleanup()

	print("%d/%d passed" % (sum(PASSED), len(PASSED)))
	if not all(PASSED):
		raise AssertionError("waiter checkin suite failed")
