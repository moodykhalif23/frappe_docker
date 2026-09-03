"""Local test sites: bank a stale shift (opened on an earlier date) and open
today's, so no "Yesterday's shift is still open" modal sits over the suites.
Runs on the manager; never point it at a live site."""
import json
import frappe
from restaurant_management import house


def run():
	frappe.set_user("geff@etham.co.ke")
	shift = house.house_shift()
	today = str(frappe.utils.today())
	if shift and not str(shift.get("period_start_date") or "").startswith(today):
		house.close_day(force=1)
		frappe.db.commit()
		print("DAY stale shift banked")
	if not house.house_shift():
		house.open_day(balances=json.dumps({"Cash": 5000}))
		frappe.db.commit()
		print("DAY opened")
	else:
		print("DAY already open today")
