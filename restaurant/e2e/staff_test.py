# The floor's PIN pad as the shift clock: link a waiter to an Employee, sign in,
# and the attendance record should be there. Requires hrms.

import frappe
from frappe.utils import add_days, today

from restaurant_management import house

EMP_NAME = "Turn Test Waiter"
WAITER_PIN = "4917"


def _cleanup():
	for w in frappe.get_all("Restaurant Waiter", filters={"waiter_name": EMP_NAME}, fields=["name"]):
		frappe.delete_doc("Restaurant Waiter", w.name, force=1, ignore_permissions=True)
	for e in frappe.get_all("Employee", filters={"employee_name": EMP_NAME}, fields=["name"]):
		if house._has_hrms():
			for c in frappe.get_all("Employee Checkin", filters={"employee": e.name}, fields=["name"]):
				frappe.delete_doc("Employee Checkin", c.name, force=1, ignore_permissions=True)
		frappe.db.set_value("Employee", e.name, "status", "Left", update_modified=False)
		frappe.delete_doc("Employee", e.name, force=1, ignore_permissions=True)
	frappe.db.commit()


def _make_employee():
	company = frappe.defaults.get_global_default("company") or frappe.get_all("Company", limit=1)[0].name
	doc = frappe.get_doc({
		"doctype": "Employee",
		"employee_name": EMP_NAME,
		"first_name": "Turn",
		"last_name": "Waiter",
		"gender": frappe.db.get_value("Gender", {"name": "Female"}) or frappe.get_all("Gender", limit=1)[0].name,
		"date_of_birth": add_days(today(), -365 * 25),
		"date_of_joining": add_days(today(), -30),
		"company": company,
		"designation": _designation(),
		"status": "Active",
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def _designation():
	name = "Waiter"
	if not frappe.db.exists("Designation", name):
		frappe.get_doc({"doctype": "Designation", "designation_name": name}).insert(ignore_permissions=True)
	return name


def run():
	results = []

	def check(label, cond, detail=""):
		results.append((bool(cond), label, detail))

	check("hrms is installed", house._has_hrms(), str(frappe.get_installed_apps()))
	if not house._has_hrms():
		return _report(results)

	_cleanup()
	employee = _make_employee()
	check("an employee record exists", frappe.db.exists("Employee", employee), employee)

	waiter = frappe.get_doc({
		"doctype": "Restaurant Waiter",
		"waiter_name": EMP_NAME,
		"pin": WAITER_PIN,
		"active": 1,
	})
	waiter.insert(ignore_permissions=True)
	frappe.db.commit()

	house.link_employee(waiter.name, employee)
	check("the waiter carries the employee link",
		frappe.db.get_value("Restaurant Waiter", waiter.name, "employee") == employee)

	signed = house.waiter_sign_in(waiter.name, WAITER_PIN)
	check("signing in returns a token", signed.get("token"))
	check("signing in writes a checkin", signed.get("checkin"), str(signed.get("checkin")))

	log = house._last_log(employee)
	check("the checkin reads IN", log and log["log_type"] == "IN", str(log))

	roster = {r["waiter"]: r for r in house.staff()}
	me = roster.get(waiter.name)
	check("the roster lists the waiter", me, str(bool(me)))
	if me:
		check("the roster shows them on shift", me["on_shift"], str(me["on_shift"]))
		check("the roster carries the designation", me["designation"] == "Waiter", me["designation"])

	again = house.waiter_sign_in(waiter.name, WAITER_PIN)
	check("signing in twice does not double-clock", again.get("checkin") == signed.get("checkin"),
		f"{signed.get('checkin')} vs {again.get('checkin')}")

	out = house.waiter_sign_out(waiter.name, pin=WAITER_PIN)
	check("signing out writes an OUT", out.get("checkin"), str(out.get("checkin")))
	log = house._last_log(employee)
	check("the last log reads OUT", log and log["log_type"] == "OUT", str(log))

	roster = {r["waiter"]: r for r in house.staff()}
	check("the roster shows them off shift", not roster[waiter.name]["on_shift"])

	_cleanup()
	return _report(results)


def _report(results):
	failed = [r for r in results if not r[0]]
	for ok, label, detail in results:
		print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f"   [{detail}]" if detail else ""))
	print(f"\n{len(results) - len(failed)}/{len(results)} passed")
	if failed:
		raise AssertionError(f"{len(failed)} staff checks failed")
	return "ok"
