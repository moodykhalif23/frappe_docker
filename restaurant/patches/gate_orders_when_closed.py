# A closed counter took new checks anyway: the pad's + button and every check
# creation path run through Restaurant Object.add_order, which never asked.
P = "apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_object/restaurant_object.py"

src = open(P).read()
if "counter is closed" in src:
    print("closed gate: already applied")
    raise SystemExit

OLD = '''    def add_order(self, client=None, from_crm=None):
        # last_user = self.current_user
        self.validate_transaction(frappe.session.user, from_crm)'''
NEW = '''    def add_order(self, client=None, from_crm=None):
        # No open shift, no new checks — food fired now could never be billed.
        if not frappe.db.exists("POS Opening Entry", {"status": "Open", "docstatus": 1}):
            frappe.throw(_("The counter is closed. A manager opens the day before orders can be taken."))
        # last_user = self.current_user
        self.validate_transaction(frappe.session.user, from_crm)'''

if OLD not in src:
    raise SystemExit("closed gate: add_order anchor not found")
open(P, "w").write(src.replace(OLD, NEW, 1))
print("closed gate: no new checks on a closed counter")
