# rm_closing_once: one POS Closing Entry per shift.
#
# erpnext posts a closing's books in a background job that it queues inside the
# closing's own transaction. Since the daily report email (10 Oct) renders a PDF
# during the submit, the commit comes seconds later and the job usually starts
# first: "Could not find POS Closing Entry", the shift stays Open, and the next
# close banks it again (and emails the report again).
#
# 1. the job is queued after the commit, so it always finds the closing;
# 2. every submit of a POS Closing Entry refuses a second one for the same shift
#    (house.refuse_second_closing); close_day/open_day finish a stuck one instead.
import sys

sys.path.insert(0, "/tmp")
from _patchlib import once  # noqa: E402

MERGE = "apps/erpnext/erpnext/accounts/doctype/pos_invoice_merge_log/pos_invoice_merge_log.py"
ANCHOR = "\t\t\tjob_id=job_id,\n\t\t\tnow=frappe.conf.developer_mode or frappe.in_test,\n"


def after_commit(s):
	if s.count(ANCHOR) != 1:
		raise SystemExit("closing once: enqueue_job anchor is not unique in " + MERGE)
	return s.replace(ANCHOR, "\t\t\tjob_id=job_id,\n"
	                 "\t\t\t# rm_closing_once: the job reads the closing, so it must not start before that commits\n"
	                 "\t\t\tenqueue_after_commit=True,\n"
	                 "\t\t\tnow=frappe.conf.developer_mode or frappe.in_test,\n", 1)


once(MERGE, "rm_closing_once", after_commit, "closing once: merge job after commit")

HOOKS = "apps/restaurant_management/restaurant_management/hooks.py"


def hook(s):
	return s.rstrip("\n") + '''

# rm_closing_once: one closing per shift, whoever submits it
doc_events = globals().get("doc_events") or {}
doc_events.setdefault("POS Closing Entry", {})["before_submit"] = "restaurant_management.house.refuse_second_closing"
'''


once(HOOKS, "rm_closing_once", hook, "closing once: before_submit hook")
