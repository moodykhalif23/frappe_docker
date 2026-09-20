# rm_unsent_at_payment — a bill must not quietly swallow a dish the kitchen was
# never told about.
#
# Measured over the four days after rounds shipped: 110 of 149 paid checks had
# NOTHING fired — 226 lines billed without the kitchen hearing of them through
# the system, and only ONE line in that whole period ever moved past "Sent". The
# food reached the table regardless, so the loss is in the record, not on the
# plate: the reports, the waiter's book and the customer tracker read those
# lines as "Attending" for ever.
#
# What to DO about it is a floor decision, not an engineering one, because
# payment happens at two completely different moments here:
#
#   * 33 of those 110 checks were paid within two minutes of being opened —
#     counter service. The food is not made yet and sending it is exactly right.
#   * 57 sat open past half an hour. The biggest single category of never-sent
#     lines is Tea & Infusions (99 of them), poured and handed over instantly.
#     Sending those at payment puts a ticket up for a drink already drunk — a
#     cook instruction for food that is on the table. That is the precise
#     failure this app has spent a fortnight eliminating.
#
# So the behaviour is a setting, and it defaults to the option that cannot cause
# a re-cook. Either way the cashier is told, which is the part that changes how
# the floor behaves.
import ast

P = ('apps/restaurant_management/restaurant_management/restaurant_management/'
     'doctype/table_order/table_order.py')
GUARD = "rm_unsent_at_payment"

s = open(P).read()
before = s

A = '''    def make_invoice(self, mode_of_payment, references=None):
        if self.link_invoice:
            return frappe.throw(_("The order has been invoiced"))
'''
if A in s and GUARD not in s:
    assert s.count(A) == 1, "make_invoice anchor %d" % s.count(A)
    s = s.replace(A, A + '''
        # rm_unsent_at_payment: settle anything the kitchen was never told about
        # BEFORE the bill is built, so the invoice sees final statuses. Wrapped
        # because a paid invoice must never fail over bookkeeping.
        try:
            self._rm_settle_unsent()
        except Exception:
            frappe.log_error(title="unsent lines at payment")
''', 1)

B = '''    def transfer(self, table, client):'''
if B in s and "_rm_settle_unsent" in s and "def _rm_settle_unsent" not in s:
    assert s.count(B) == 1, "transfer anchor %d" % s.count(B)
    s = s.replace(B, '''    def _rm_settle_unsent(self):
        """rm_unsent_at_payment: deal with lines that never reached the kitchen.

        Three behaviours, chosen on Restaurant Settings:

          "Record as served" (default) - close them where the board can never
              see them. The record stops lying; no ticket is ever raised for
              food that is already eaten. They keep kot_round 0, which is what
              tells them apart later from a line that was genuinely fired.
          "Send to kitchen" - the literal auto-fire: the real fire path, so they
              get a round, a waiter, a ticket and the realtime push. Right for a
              counter-service house; a re-cook instruction for a dine-in one.
          "Leave as is" - what happened before this existed.

        The cashier is told the count either way. That is the half that changes
        what the floor does tomorrow."""
        unsent = [i for i in self.entry_items
                  if (i.qty or 0) > 0
                  and i.status in (status_attending, "Pending", "", None)]
        if not unsent:
            return

        mode = (frappe.db.get_single_value("Restaurant Settings", "rm_unsent_at_payment")
                or "Record as served")
        if mode == "Leave as is":
            return

        frappe.msgprint(
            _("{0} item(s) on this bill were never sent to the kitchen.").format(len(unsent)),
            indicator="orange", alert=True)

        if mode == "Send to kitchen":
            self.send          # the real path: round, waiter, board, realtime
            self.reload()
            return

        # "Record as served": the terminal status sits outside every production
        # centre's managed list, so these can never surface as a card.
        terminal = _RM_FLOW[-1]
        if not frappe.db.exists("Status Order PC", terminal):
            return
        has_waiter = frappe.db.has_column("Order Entry Item", "waiter")
        now = frappe.utils.now_datetime()
        for i in unsent:
            values = {"status": terminal, "ordered_time": i.ordered_time or now}
            if has_waiter and not i.get("waiter"):
                values["waiter"] = self.get("waiter")
            frappe.db.set_value("Order Entry Item", i.name, values, update_modified=False)
        self.reload()

    def transfer(self, table, client):''', 1)

ast.parse(s)
assert s.count(GUARD) >= 2, "guard count %d" % s.count(GUARD)
assert "def _rm_settle_unsent" in s, "the method did not land"
if s != before:
    open(P, "w").write(s)
    print("unsent_at_payment: patched")
else:
    print("unsent_at_payment: already current")
