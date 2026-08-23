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
