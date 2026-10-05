# rm_till_withdrawal: the owners' phone page. Paste the Safaricom SMS, check what
# was read, press Record — it posts the withdrawal and its journal entry at once.
import frappe
import frappe.sessions  # get_csrf_token; imported by the request path anyway, said here on purpose
from frappe.utils import now_datetime

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/till-withdrawal"
		raise frappe.Redirect
	settings = "Restaurant Settings"
	context.no_breadcrumbs = True
	context.show_sidebar = False
	context.title = "Till withdrawal"
	context.can_record = all(frappe.has_permission("Till Withdrawal", p) for p in ("create", "submit"))
	context.has_bank = bool(frappe.db.get_value(settings, settings, "rm_tw_bank_account"))
	context.now_local = now_datetime().strftime("%Y-%m-%dT%H:%M")
	context.csrf = frappe.sessions.get_csrf_token()
	context.recent = frappe.get_list(
		"Till Withdrawal", filters={"docstatus": 1}, order_by="withdrawn_at desc", limit_page_length=8,
		fields=["reference", "amount", "transaction_cost", "withdrawn_at", "mode_of_payment", "purpose"],
	) if context.can_record else []
	return context
