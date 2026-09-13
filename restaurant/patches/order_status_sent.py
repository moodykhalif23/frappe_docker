# A fired check never reached the kitchen screen.
#
# `send` flips each Order Entry Item to "Sent" but leaves the Table Order at
# "Attending". The production-center board runs with group_items_by_order=1,
# which applies _status_managed (Sent/Processing/Completed) to the PARENT
# order's status - so every fired check was filtered out and the kitchen saw
# nothing. Upstream clearly expects the order to reach "Sent": notify_status()
# announces "Order ... has been sent to kitchen" on exactly that transition and
# validate() guards against sending an empty one.
#
# Carry the order itself to "Sent" once its lines are fired. Idempotent.
p = "apps/restaurant_management/restaurant_management/restaurant_management/doctype/table_order/table_order.py"
s = open(p).read()

MARK = "rm_order_status_sent"
if MARK in s:
    print("order_status_sent: already patched")
else:
    old = (
        '        self.reload()\n'
        '        #self.synchronize_data = dict(status=["Sent"])\n'
        '        self.synchronize(dict(status=["Sent"]))\n'
    )
    new = (
        '        self.reload()\n'
        '        # rm_order_status_sent: the board groups by order and filters on the\n'
        '        # ORDER status, so firing only the lines left the check invisible to\n'
        '        # the kitchen. Carry the order to Sent, as notify_status() expects.\n'
        '        if items_to_return and self.status not in ("Invoiced", "Cancelled"):\n'
        '            self.status = "Sent"\n'
        '            self.save()\n'
        '            self.reload()\n'
        '        #self.synchronize_data = dict(status=["Sent"])\n'
        '        self.synchronize(dict(status=["Sent"]))\n'
    )
    assert s.count(old) == 1, "anchor count=%d" % s.count(old)
    open(p, "w").write(s.replace(old, new, 1))
    print("order_status_sent: patched")
