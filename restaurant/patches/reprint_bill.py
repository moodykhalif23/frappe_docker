# A bill that failed to print was unreachable once the check was invoiced
# (make_invoice sets show_in_pos = 0, so it drops off the pad with its Account
# button). Adds house.recent_bills + a "Reprint a bill" floor-menu dialog.
#
# Version-aware: the module is REPLACED when an older build is baked in,
# otherwise a stale copy would survive every future bake. Idempotent.
RM = 'apps/restaurant_management/restaurant_management'
NEW = open('/tmp/reprint.js').read()
CURRENT = '__v3: true'
MARK = '// rm_reprint: a bill that failed to print'
MENU_MARK = 'add_menu_item(__("Reprint a bill")'

# --- 1. server: recent_bills ---
p1 = RM + '/house.py'
s = open(p1).read()
if 'def recent_bills(' in s:
    print('reprint_bill: recent_bills already present')
else:
    s = s.rstrip('\n') + '\n' + '''

@frappe.whitelist()
def recent_bills(limit=25):
\t"""Recent checks so a bill that failed to print can be run again.

\tPaid checks carry their invoice (reprint the receipt); open ones do not
\t(reprint the order bill)."""
\ttry:
\t\tlimit = min(int(limit or 25), 50)
\texcept (TypeError, ValueError):
\t\tlimit = 25
\trows = frappe.db.sql("""
\t\tselect t.name as `order`, t.link_invoice as invoice,
\t\t       t.table_description as `table`, t.customer_name as guest,
\t\t       t.amount as amount, t.modified as modified
\t\tfrom `tabTable Order` t
\t\twhere ifnull(t.status, '') not in ('Cancelled', '')
\t\torder by t.modified desc
\t\tlimit %s
\t""", (limit,), as_dict=True)
\tout = []
\tfor r in rows:
\t\tout.append({
\t\t\t"order": r.get("order"),
\t\t\t"invoice": r.get("invoice") or "",
\t\t\t"table": r.get("table") or "",
\t\t\t"guest": r.get("guest") or "",
\t\t\t"amount": frappe.utils.fmt_money(r.get("amount") or 0),
\t\t\t"time": frappe.utils.format_datetime(r.get("modified"), "dd/MM HH:mm"),
\t\t})
\treturn out
'''
    open(p1, 'w').write(s)
    import ast; ast.parse(open(p1).read())
    print('reprint_bill: recent_bills added')

# --- 2. client module: replace any older build ---
p2 = RM + '/restaurant_management/page/restaurant_manage/restaurant_manage.js'
j = open(p2).read()
if CURRENT in j:
    print('reprint_bill: module already current')
else:
    i = j.find(MARK)
    if i != -1:
        j = j[:i].rstrip('\n') + '\n' + NEW
        print('reprint_bill: module REPLACED with current build')
    else:
        j = j.rstrip('\n') + '\n' + NEW
        print('reprint_bill: module appended')

# --- 3. the floor menu item (guard on the CALL, not the label: the dialog
#        title uses the same words and would false-positive) ---
if MENU_MARK in j:
    print('reprint_bill: menu item already present')
else:
    anchor = 'rm.page.add_menu_item(__("Release a table"), () => RM_seats.release_dialog());'
    assert j.count(anchor) == 1, 'menu anchor %d' % j.count(anchor)
    j = j.replace(anchor, anchor + '\n      }\n'
                  '      if (rm && rm.page && rm.page.add_menu_item && CAN_BILL) {\n'
                  '        rm.page.add_menu_item(__("Reprint a bill"), () => window.RM_reprint && RM_reprint.open());', 1)
    print('reprint_bill: menu item added')

open(p2, 'w').write(j)
