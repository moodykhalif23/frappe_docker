# A bill's payment method is in a child table, which a list view cannot show. Summarise
# it onto the invoice itself so Cash, Card and M-Pesa are readable at a glance.
H = "apps/restaurant_management/restaurant_management/hooks.py"
src = open(H).read()

if "rm_payment_modes" in src:
    print("payment modes: hooks already applied")
else:
    src = src.rstrip("\n") + '''

# rm_payment_modes: stamp how a bill was paid onto the invoice, for the list view
for _dt in ("Sales Invoice", "POS Invoice"):
    doc_events = globals().get("doc_events") or {}
    _ev = doc_events.setdefault(_dt, {})
    _existing = _ev.get("on_submit")
    _new = "restaurant_management.house.stamp_payment_modes"
    if _existing:
        _ev["on_submit"] = ([_existing] if isinstance(_existing, str) else list(_existing)) + [_new]
    else:
        _ev["on_submit"] = _new
'''
    open(H, "w").write(src)
    print("payment modes: on_submit hook registered")

import ast
ast.parse(open(H).read())
