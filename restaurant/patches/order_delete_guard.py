# rm_delete_guard — deleting a check could erase food the kitchen had cooked.
#
# TableOrder._delete called normalize_data() first. That method does
#
#     self.entry_items = []
#     for item in self.entry_items:      # <- the list it just emptied
#         ...
#     self.save()
#
# so the loop body never ran, and save() on an emptied child table makes frappe
# DELETE every Order Entry Item row for the check. Both guards on the path were
# defeated by that one line:
#
#   * `len(self.entry_items) > self.products_not_ordered_count` then compared
#     0 > 0 and let everything through;
#   * house.refuse_delete (wired as on_trash, rm_no_deleting_money) counts the
#     check's fired lines in the DATABASE — and they had just been deleted.
#
# Net effect: the pad's trash button erased any check, including one whose food
# the kitchen had already cooked and served, along with every record of it.
#
# Fix: judge the check BEFORE anything is rewritten, and stop normalizing the
# children of a document that is about to be deleted — frappe removes child rows
# with the parent, and that save() would now reach calculate_order()/get_invoice(),
# which can throw and would turn a working delete into a failing one.
# normalize_data itself is repaired too: left as it was it is a landmine for
# whatever calls it next.
import ast

P = ('apps/restaurant_management/restaurant_management/restaurant_management/'
     'doctype/table_order/table_order.py')
GUARD = "rm_delete_guard"

s = open(P).read()
before = s

# Each edit below is guarded on its OWN output. A single guard at the top of the
# file would mean that adding a fix here later silently skips on any image that
# already carries the earlier ones — the exact trap PATCH_MANIFEST exists to
# catch, and it has bitten this pipeline twice.

A = '''    @property
    def _delete(self):
        self.normalize_data()
        if len(self.entry_items) > self.products_not_ordered_count:
            frappe.throw(_("There are ordered products, you cannot delete"))

        self.delete()'''
if A in s:
    assert s.count(A) == 1, "_delete anchor %d" % s.count(A)
    s = s.replace(A, '''    @property
    def _delete(self):
        # rm_delete_guard: judge the check BEFORE anything is rewritten.
        # This used to call normalize_data() first, which emptied entry_items
        # and then iterated the list it had just emptied — so the loop body
        # never ran and save() wiped every child row out of the database. That
        # defeated BOTH guards at once: the count here compared 0 > 0, and
        # house.refuse_delete (on_trash) counted the fired lines that had just
        # been deleted and found none. A check whose food the kitchen had
        # already cooked could be deleted from the pad, record and all.
        #
        # normalize_data() is deliberately NOT called any more: frappe deletes
        # child rows with their parent, so it bought nothing, and now that its
        # loop works its save() would reach calculate_order() -> get_invoice(),
        # which can throw and would turn a working delete into a failing one.
        fired = [i for i in self.entry_items
                 if (i.qty or 0) > 0
                 and i.status not in (status_attending, "Pending", "", None)]
        if fired:
            frappe.throw(_(
                "This check has {0} item(s) already sent to the kitchen. Use Release on"
                " the floor, which voids it and keeps the record — deleting hides food"
                " that was cooked.").format(len(fired)))

        self.delete()''', 1)

B = '''    def normalize_data(self):
        self.entry_items = []
        for item in self.entry_items:
            if item.qty > 0:'''
if B in s:
    assert s.count(B) == 1, "normalize_data anchor %d" % s.count(B)
    s = s.replace(B, '''    def normalize_data(self):
        # rm_delete_guard: iterate a COPY. This cleared entry_items and then
        # looped over the list it had just cleared, so instead of dropping the
        # empty rows it dropped every row there was — and the save() below made
        # that permanent.
        _rows = list(self.entry_items)
        self.entry_items = []
        for item in _rows:
            if (item.qty or 0) > 0:''', 1)

C = '''                    has_serial_no=item.has_serial_no,
                    serial_no=item.serial_no,
                ))
        self.save()'''
if C in s:
    assert s.count(C) == 1, "normalize append anchor %d" % s.count(C)
    s = s.replace(C, '''                    has_serial_no=item.has_serial_no,
                    serial_no=item.serial_no,
                    # rm_delete_guard: this is another explicit kwarg list that
                    # rebuilds every row, so it eats anything it does not name
                    kot_round=item.get("kot_round") or 0,
                    waiter=item.get("waiter"),
                ))
        self.save()''', 1)

# normalize_data's loop body had NEVER run in this frappe version — a child
# Document is not subscriptable, so `item["item_tax_template"]` raises
# TypeError. It went unnoticed because the loop iterated a list the line above
# had just emptied, so the body was unreachable dead code. Repairing the loop
# exposed it. Guarded separately: this line is broken independently of the
# block above, and an image may already carry that block without this fix.
D = '                    item_tax_template=item["item_tax_template"],'
if D in s:
    assert s.count(D) == 1, "item_tax_template anchor %d" % s.count(D)
    s = s.replace(D, '                    # rm_delete_guard: a child Document is not subscriptable\n'
                     '                    item_tax_template=item.get("item_tax_template"),', 1)

ast.parse(s)
assert s.count(GUARD) >= 3, "guard count %d" % s.count(GUARD)
assert 'item_tax_template=item.get(' in s, "the subscript fix did not land"
if s != before:
    open(P, "w").write(s)
    print("order_delete_guard: patched")
else:
    print("order_delete_guard: already current")
