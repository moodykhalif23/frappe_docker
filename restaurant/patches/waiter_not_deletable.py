# Deleting a waiter poisons the books: their name stays on every check and
# invoice as a Link, and consolidation at close re-saves each invoice, so link
# validation fails and the day can never be banked. Staff who leave are
# deactivated, never deleted — now the system holds that line itself.
P = ("apps/restaurant_management/restaurant_management/restaurant_management/"
     "doctype/restaurant_waiter/restaurant_waiter.py")

src = open(P).read()
if "rm_waiter_has_history" in src:
    print("waiter delete: already applied")
    raise SystemExit

if "class RestaurantWaiter(Document):" not in src:
    raise SystemExit("waiter delete: controller class not found")

BLOCK = '''
\tdef on_trash(self):
\t\t# rm_waiter_has_history: their name is a Link on every check they served
\t\tserved = []
\t\tfor doctype in ("POS Invoice", "Sales Invoice", "Table Order", "Restaurant Booking"):
\t\t\tif not frappe.db.has_column(doctype, "waiter"):
\t\t\t\tcontinue
\t\t\tcount = frappe.db.count(doctype, {"waiter": self.name})
\t\t\tif count:
\t\t\t\tserved.append("%d %s" % (count, doctype))
\t\tif served:
\t\t\tfrappe.throw(frappe._(
\t\t\t\t"{0} has history on this system ({1}). Untick Active instead of deleting —"
\t\t\t\t" their past sales keep their name."
\t\t\t).format(self.waiter_name or self.name, ", ".join(served)))
'''

open(P, "w").write(src.rstrip() + "\n" + BLOCK)
print("waiter delete: a waiter with history cannot be deleted")
