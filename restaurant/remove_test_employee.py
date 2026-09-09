"""Remove the test fixture that `staff_test.py` left on the live site, and unlink the
real waiters that were pointed at it. Safe to re-run: it finds nothing on a second run.

    ssh <host> "docker exec -i <backend> bash -lc 'cat > /tmp/rm_emp.py'" \
        < restaurant/remove_test_employee.py
    ssh <host> "echo 'exec(open(\"/tmp/rm_emp.py\").read(), globals()); run()' \
        | docker exec -i <backend> bench --site <site> console"

`staff_test.py` ran against frappe.ikobriq.com once, on 2026-08-25. It creates an
Employee with first_name "Turn" and last_name "Waiter"; frappe rebuilds employee_name
from those parts, so the record stored as "Turn Waiter" while the suite's own teardown
looked for "Turn Test Waiter" and never matched. Everything else that run created was
removed — that day left no waiter, booking, check or invoice behind.

It became load-bearing by accident: it was the only Employee on the site, so when the
three real waiters were set up on 2026-09-06 they were all linked to it. Attendance has
never recorded a row, so nothing is lost by unlinking them — but until each waiter has
an Employee of their own, none of them can clock in. Sales attribution is unaffected:
that credits the Restaurant Waiter, not the Employee.

The suite's teardown is fixed, so this cannot recur.
"""
import json

import frappe

LEAKED = {"employee_name": ["in", ["Turn Test Waiter", "Turn Waiter"]],
		  "date_of_joining": ["<=", "2026-08-25"]}


def run():
	audit = {"unlinked_waiters": [], "employees_removed": [], "refused": []}

	for emp in frappe.get_all("Employee", filters=LEAKED, fields=["name", "employee_name"]):
		# only the fixture is in scope: anything with real HR history is left alone
		history = {dt: frappe.db.count(dt, {"employee": emp.name}) for dt in
				   ("Employee Checkin", "Attendance", "Shift Assignment",
					"Salary Structure Assignment", "Leave Allocation")}
		if any(history.values()):
			audit["refused"].append({"employee": emp.name, "why": "has HR history",
									 "history": history})
			continue

		for w in frappe.get_all("Restaurant Waiter", filters={"employee": emp.name},
								fields=["name", "waiter_name"]):
			frappe.db.set_value("Restaurant Waiter", w.name, "employee", None,
								update_modified=False)
			frappe.get_doc("Restaurant Waiter", w.name).add_comment("Comment", frappe._(
				"Unlinked from employee {0} ({1}), which was a test fixture left on this site by"
				" an end-to-end suite run on 2026-08-25, not a real member of staff. Three waiters"
				" shared it, so attendance would have clocked them all as one person. Sales"
				" attribution is unaffected. Link a real Employee record to enable clocking in."
			).format(emp.name, emp.employee_name))
			audit["unlinked_waiters"].append({"waiter": w.name, "was": emp.name})

		frappe.db.set_value("Employee", emp.name, "status", "Left", update_modified=False)
		frappe.delete_doc("Employee", emp.name, force=1, ignore_permissions=True)
		audit["employees_removed"].append({"employee": emp.name, "name": emp.employee_name})

	frappe.db.commit()
	print("REMOVED", json.dumps(audit, default=str))
	print("EMPLOYEES_LEFT", json.dumps(frappe.get_all(
		"Employee", fields=["name", "employee_name", "status"]), default=str))
	print("WAITERS_NOW", json.dumps(frappe.get_all(
		"Restaurant Waiter", fields=["name", "employee"], order_by="name"), default=str))
