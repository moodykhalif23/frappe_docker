# rm_till_withdrawal — money an owner takes out of a till (the M-Pesa till or the
# cash drawer) in the middle of a shift.
#
# Why: the owners withdraw from the M-Pesa till during the day and nothing
# recorded it. The close reconciled against opening + sales, so the till looked
# short by every withdrawal (or, since the count was pre-filled, looked exact and
# the gap surfaced next morning as an unexplained drop in the opening balance —
# KES 218k over 12 days to 4 Oct 2026). The books never moved either: the ledger
# held KES 376k of M-Pesa against a till of ~27k.
#
# A withdrawal is recorded from the owner's phone (/till-withdrawal, paste the
# Safaricom SMS) or at the till (the POS Withdrawal button). On submit it posts a
# Journal Entry: Dr the account it went to (Owner's Drawings, a bank, or one the
# accountant picks) and Bank Charges for Safaricom's fee; Cr the till's account.
# Cancelling it cancels that Journal Entry. The close and the daily report take
# recorded withdrawals off the expected balance.

import re
from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, fmt_money, get_datetime, getdate, now_datetime

SETTINGS = "Restaurant Settings"
PURPOSE_ACCOUNT = {"Owner withdrawal": "rm_tw_drawings_account", "Bank settlement": "rm_tw_bank_account"}

_MONEY = r"(?:Ksh|KES)\s?([\d,]+(?:\.\d{1,2})?)"
_CODE = re.compile(r"\b([A-Z0-9]{10})\b")
_AMOUNT = re.compile(_MONEY, re.I)
_WHEN = re.compile(r"\bon\s+(\d{1,2})/(\d{1,2})/(\d{2,4})\s+at\s+(\d{1,2}):(\d{2})\s*([AP]M)?", re.I)
_BALANCE = re.compile(r"balance\s+is\s+" + _MONEY, re.I)
_COST = re.compile(r"transaction\s+cost,?\s+" + _MONEY, re.I)


def _money(s):
	return flt((s or "").replace(",", ""))


def parse_sms(text):
	"""Read a Safaricom SMS: code, amount, time, charge and the balance after.

	Safaricom's wording varies by product, so this looks for the parts, not a
	template: the first 10-character code with letters AND digits, the first
	"Ksh" amount that is not the balance or the charge, "on d/m/yy at h:mm PM".
	Anything it cannot find is left for the person to type."""
	text = (text or "").strip()
	out = {"reference": None, "amount": None, "withdrawn_at": None,
		   "transaction_cost": None, "balance_after": None, "warnings": []}
	if not text:
		return out
	for m in _CODE.finditer(text):
		code = m.group(1)
		if re.search(r"[A-Z]", code) and re.search(r"\d", code):
			out["reference"] = code
			break
	skip = []
	for rx, key in ((_BALANCE, "balance_after"), (_COST, "transaction_cost")):
		m = rx.search(text)
		if m:
			out[key] = _money(m.group(1))
			skip.append(m.span(1))
	for m in _AMOUNT.finditer(text):
		if not any(a <= m.start(1) < b for a, b in skip):
			out["amount"] = _money(m.group(1))
			break
	m = _WHEN.search(text)
	if m:
		d, mo, y, h, mi, ampm = m.groups()
		y = int(y) + (2000 if len(y) == 2 else 0)
		h = int(h)
		if ampm:  # 12:30 AM is 00:30, 12:30 PM is 12:30
			h = h % 12 + (12 if ampm.upper() == "PM" else 0)
		try:
			out["withdrawn_at"] = datetime(y, int(mo), int(d), h, int(mi)).strftime("%Y-%m-%d %H:%M:%S")
		except ValueError:
			pass
	if re.search(r"\breceived\b", text, re.I) and not re.search(r"withdraw|transferred|sent\s+to", text, re.I):
		out["warnings"].append(_("This looks like money received, not a withdrawal."))
	return out


def default_company():
	return (frappe.defaults.get_user_default("Company")
			or frappe.defaults.get_global_default("company")
			or frappe.db.get_value("Company", {}, "name"))


def till_account(mode_of_payment, company):
	return frappe.db.get_value("Mode of Payment Account",
							   {"parent": mode_of_payment, "company": company}, "default_account")


def shift_at(company, when):
	"""The POS shift a moment fell in: an open one, or a closed one spanning it."""
	when = get_datetime(when)
	row = frappe.db.sql("""
		select o.name from `tabPOS Opening Entry` o
		left join `tabPOS Closing Entry` c on c.name = o.pos_closing_entry and c.docstatus = 1
		where o.docstatus = 1 and o.company = %(co)s and o.period_start_date <= %(t)s
		  and (o.status = 'Open' or c.period_end_date >= %(t)s)
		order by o.period_start_date desc limit 1""", {"co": company, "t": when})
	return row[0][0] if row else None


def withdrawn_between(company, mode_of_payment, start, end=None):
	"""Submitted withdrawals from one till in a time window: (total out, rows).
	The total includes Safaricom's charge, because that left the till too."""
	if not start or not frappe.db.table_exists("Till Withdrawal"):
		return 0.0, []
	filters = [["docstatus", "=", 1], ["company", "=", company],
			   ["mode_of_payment", "=", mode_of_payment], ["withdrawn_at", ">=", get_datetime(start)]]
	if end:
		filters.append(["withdrawn_at", "<=", get_datetime(end)])
	rows = frappe.get_all("Till Withdrawal", filters=filters, order_by="withdrawn_at asc",
						  fields=["name", "reference", "amount", "transaction_cost", "withdrawn_at",
								  "purpose", "withdrawn_by"])
	return round(sum(flt(r.amount) + flt(r.transaction_cost) for r in rows), 2), rows


class TillWithdrawal(Document):
	def validate(self):
		self.reference = re.sub(r"\s+", "", self.reference or "").upper()
		if not self.company:
			self.company = default_company()
		if flt(self.amount) <= 0:
			frappe.throw(_("Enter the amount that was withdrawn."))
		if flt(self.transaction_cost) < 0:
			frappe.throw(_("The Safaricom charge cannot be negative."))
		cash = frappe.db.get_value("Mode of Payment", self.mode_of_payment, "type") == "Cash"
		if not cash and not re.fullmatch(r"[A-Z0-9]{10}", self.reference):
			frappe.throw(_("An M-Pesa code is 10 letters and digits, like UJ5AB12CD3. Check the SMS."))
		if get_datetime(self.withdrawn_at) > now_datetime() + timedelta(minutes=15):
			frappe.throw(_("The withdrawal time is in the future."))
		# one record per M-Pesa code; a cancelled one may be redone (amended)
		dup = frappe.db.get_value("Till Withdrawal",
								  {"reference": self.reference, "docstatus": ["<", 2], "name": ["!=", self.name]},
								  ["name", "amount", "withdrawn_at"], as_dict=True)
		if dup:
			frappe.throw(_("{0} is already recorded: {1}, {2} at {3}.").format(
				self.reference, dup.name, fmt_money(dup.amount),
				frappe.utils.format_datetime(dup.withdrawn_at, "dd/MM HH:mm")), title=_("Already recorded"))
		if not self.account:
			field = PURPOSE_ACCOUNT.get(self.purpose)
			self.account = field and frappe.db.get_value(SETTINGS, SETTINGS, field) or None
		if not self.recorded_by:
			self.recorded_by = frappe.session.user
		self.pos_opening_entry = shift_at(self.company, self.withdrawn_at)

	def before_submit(self):
		if not self.account:
			frappe.throw(_("Choose the account the money went to. Restaurant Settings › Till withdrawals "
						   "sets the default for each purpose."), title=_("No account"))
		if not till_account(self.mode_of_payment, self.company):
			frappe.throw(_("The {0} till has no account for {1}. Set it on the Mode of Payment.").format(
				self.mode_of_payment, self.company))

	def on_submit(self):
		self.db_set("journal_entry", make_journal_entry(self).name)

	def on_cancel(self):
		if self.journal_entry and frappe.db.get_value("Journal Entry", self.journal_entry, "docstatus") == 1:
			je = frappe.get_doc("Journal Entry", self.journal_entry)
			je.flags.ignore_permissions = True
			je.cancel()


def make_journal_entry(tw):
	"""Dr where the money went (+ Bank Charges for the fee), Cr the till."""
	cost = flt(tw.transaction_cost)
	charges = frappe.db.get_value(SETTINGS, SETTINGS, "rm_tw_charges_account") if cost else None
	if cost and not charges:
		frappe.throw(_("Set the account for Safaricom charges in Restaurant Settings › Till withdrawals."))
	cc = frappe.get_cached_value("Company", tw.company, "cost_center")
	day = getdate(tw.withdrawn_at)
	rows = [{"account": tw.account, "debit_in_account_currency": flt(tw.amount), "cost_center": cc}]
	if cost:
		rows.append({"account": charges, "debit_in_account_currency": cost, "cost_center": cc})
	rows.append({"account": till_account(tw.mode_of_payment, tw.company),
				 "credit_in_account_currency": flt(tw.amount) + cost, "cost_center": cc})
	je = frappe.get_doc({
		"doctype": "Journal Entry", "voucher_type": "Journal Entry", "company": tw.company,
		"posting_date": day, "cheque_no": tw.reference, "cheque_date": day,
		"user_remark": _("{0} withdrawn from the {1} till, {2} ({3}){4}. Till Withdrawal {5}.").format(
			fmt_money(tw.amount), tw.mode_of_payment, tw.reference, tw.purpose,
			(_(" by {0}").format(tw.withdrawn_by) if tw.withdrawn_by else ""), tw.name),
		"accounts": rows,
	})
	je.flags.ignore_permissions = True
	je.insert()
	je.submit()
	return je


@frappe.whitelist()
def preview(sms_text=None):
	"""What an SMS says, for the form to fill in before anything is saved."""
	out = parse_sms(sms_text)
	if out["reference"]:
		dup = frappe.db.get_value("Till Withdrawal", {"reference": out["reference"], "docstatus": ["<", 2]}, "name")
		if dup:
			out["warnings"].append(_("{0} is already recorded as {1}.").format(out["reference"], dup))
	return out


@frappe.whitelist(methods=["POST"])
def record(sms_text=None, amount=None, reference=None, withdrawn_at=None, transaction_cost=None,
		   purpose="Owner withdrawal", mode_of_payment="M-Pesa", withdrawn_by=None, note=None,
		   balance_after=None):
	"""Record and post a withdrawal in one step: the phone page and the till both
	use this. What the person typed wins over what was read from the SMS."""
	for ptype in ("create", "submit"):
		if not frappe.has_permission("Till Withdrawal", ptype):
			frappe.throw(_("Your login cannot record till withdrawals."), frappe.PermissionError)
	read = parse_sms(sms_text) if sms_text else {}
	pick = lambda typed, key: typed if typed not in (None, "") else read.get(key)
	doc = frappe.get_doc({
		"doctype": "Till Withdrawal",
		"sms_text": sms_text,
		"mode_of_payment": mode_of_payment or "M-Pesa",
		"amount": flt(pick(amount, "amount")),
		"transaction_cost": flt(pick(transaction_cost, "transaction_cost")),
		"reference": pick(reference, "reference"),
		"withdrawn_at": pick(withdrawn_at, "withdrawn_at") or now_datetime(),
		"balance_after": pick(balance_after, "balance_after"),
		"purpose": purpose or "Owner withdrawal",
		"withdrawn_by": withdrawn_by or frappe.utils.get_fullname(frappe.session.user),
		"note": note,
		"company": default_company(),
	})
	doc.insert()
	doc.submit()
	return {"name": doc.name, "amount": doc.amount, "transaction_cost": doc.transaction_cost,
			"reference": doc.reference, "withdrawn_at": str(doc.withdrawn_at),
			"journal_entry": doc.journal_entry, "shift": doc.pos_opening_entry}


@frappe.whitelist()
def recent(limit=8):
	return frappe.get_list("Till Withdrawal", filters={"docstatus": 1}, order_by="withdrawn_at desc",
						   limit_page_length=min(cint(limit) or 8, 50),
						   fields=["name", "reference", "amount", "transaction_cost", "withdrawn_at",
								   "mode_of_payment", "purpose", "withdrawn_by"])
