# An M-Pesa payment landed as an amount and nothing else. make_invoice now takes
# the codes the pay form sends, refuses an M-Pesa row without a well-formed one,
# refuses a code that already paid another invoice, and stores it as the payment
# row's reference_no — erpnext's own field, so every report can read it.
P = "apps/restaurant_management/restaurant_management/restaurant_management/doctype/table_order/table_order.py"

src = open(P).read()
if "def _rm_payment_reference" in src and "references=None" in src:
    print("mpesa reference: already applied")
    raise SystemExit

def replace_once(s, old, new, what):
    if s.count(old) != 1:
        raise SystemExit("mpesa reference: %s found %d times" % (what, s.count(old)))
    return s.replace(old, new, 1)

# helper at the module head: appended blocks are stripped and re-added each bake
if "def _rm_payment_reference" not in src:
    src = replace_once(src, 'status_attending = "Attending"\n', '''status_attending = "Attending"\n

def _rm_is_mpesa(mode_of_payment):
    import re
    return bool(re.search(r"m-?pesa", mode_of_payment or "", re.I))


def _rm_payment_reference(mode_of_payment, reference):
    """The code an M-Pesa payment must carry: ten letters and digits, never
    used before. Other modes keep whatever reference they were given."""
    import re
    code = (reference or "").strip().upper()
    if not _rm_is_mpesa(mode_of_payment):
        return code or None
    if not re.fullmatch(r"[A-Z0-9]{10}", code):
        frappe.throw(_("Enter the customer's {0} confirmation code — 10 letters and digits, as on their phone.")
                     .format(mode_of_payment))
    used = frappe.db.get_value("Sales Invoice Payment",
                               {"reference_no": code, "parenttype": ["in", ["POS Invoice", "Sales Invoice"]],
                                "docstatus": 1}, "parent")
    if used:
        frappe.throw(_("{0} code {1} already paid invoice {2}.").format(mode_of_payment, code, used))
    return code
''', "module head anchor")

src = replace_once(src, "    def make_invoice(self, mode_of_payment):\n",
                   "    def make_invoice(self, mode_of_payment, references=None):\n", "make_invoice signature")
src = replace_once(src, """        for mp in mode_of_payment:
            invoice.append('payments', dict(
                mode_of_payment=mp,
                amount=mode_of_payment[mp]
            ))
""", """        if isinstance(references, str):
            references = frappe.parse_json(references or "{}")
        for mp in mode_of_payment:
            invoice.append('payments', dict(
                mode_of_payment=mp,
                amount=mode_of_payment[mp],
                reference_no=_rm_payment_reference(mp, (references or {}).get(mp)),
            ))
""", "payments loop")
open(P, "w").write(src)
print("mpesa reference: M-Pesa rows carry a verified, unused confirmation code")
