# Order (fire-to-kitchen) button stayed greyed for a freshly-added line whose
# local status is still blank before the server sync returns: pending_count
# only counted ["Pending","Attending"], so the button waited on the server's
# products_not_ordered counter and, if that lagged, never lit. Count the blank/
# null states too, matching table_order.py which treats Pending/""/None as
# Attending-to-be. Idempotent.
p = "apps/restaurant_management/restaurant_management/public/restaurant/js/table-order-class.js"
s = open(p).read()
old = '["Pending", "Attending"].includes(i.data.status)'
new = '["Pending", "Attending", "", null, undefined].includes(i.data.status)'
if new in s:
    print("order_button_pending: already patched")
else:
    assert s.count(old) == 1, "anchor count=%d" % s.count(old)
    open(p, "w").write(s.replace(old, new, 1))
    print("order_button_pending: patched")
