# rm_divide_qty — splitting a check truncated fractional quantities.
#
#     rest = (int(item.qty) - int(divide_item["qty"]))
#
# Order Entry Item.qty is decimal(21,9) and the pad's numpad has a decimal key,
# so a line can legitimately hold 2.5 (half a portion, 1.5 kg, a shared bottle).
# int() truncated BOTH sides. Move one unit off a 2.5 line and `rest` came out 1
# instead of 1.5 — half a portion vanished off the bill, silently. Worse, when
# the truncated `rest` hit 0 the code treated the line as fully moved and re-used
# its identifier, so the remainder was not just mispriced but gone.
#
# It has never fired here: all 683 line rows and 611 invoice rows are whole
# numbers and every item is UOM "Nos". It is a landmine for the first item sold
# by weight, not an active loss. Also guards the direction nothing checked: you
# cannot move more of a line than the check actually has.
import ast

P = ('apps/restaurant_management/restaurant_management/restaurant_management/'
     'doctype/table_order/table_order.py')
GUARD = "rm_divide_qty"

s = open(P).read()
before = s

A = '''            if divide_item is not None:
                rest = (int(item.qty) - int(divide_item["qty"]))
                current_item = self.items_list(item.identifier)[0]
                current_item["qty"] = rest
                self.update_item(current_item, True, False)'''
if A in s:
    assert s.count(A) == 1, "divide rest anchor %d" % s.count(A)
    s = s.replace(A, '''            # rm_divide_qty: nothing rounds here any more. A zero-qty entry is
            # skipped rather than processed — the client only sends lines with
            # in_new_order > 0, but a zero would otherwise add an untaken line to
            # the new check while leaving the original whole.
            if divide_item is not None and frappe.utils.flt(divide_item["qty"]) > 0:
                moved = frappe.utils.flt(divide_item["qty"])
                have = frappe.utils.flt(item.qty)
                if moved > have:
                    frappe.throw(_("You cannot move {0} x {1} to the new bill —"
                                   " this check only has {2}.").format(
                        moved, item.item_name or item.item_code, have))
                rest = frappe.utils.flt(have - moved, 9)
                current_item = self.items_list(item.identifier)[0]
                current_item["qty"] = rest
                self.update_item(current_item, True, False)''', 1)

B = '''                    qty=divide_item["qty"],'''
if B in s:
    assert s.count(B) == 1, "divide qty anchor %d" % s.count(B)
    s = s.replace(B, '''                    qty=moved,  # rm_divide_qty: the coerced float, not the raw payload''', 1)

C = '''                    identifier=item.identifier if rest == 0 else divide_item["identifier"],'''
if C in s:
    assert s.count(C) == 1, "divide identifier anchor %d" % s.count(C)
    s = s.replace(C, '''                    # rm_divide_qty: the whole line moved, so the new check keeps
                    # its identity. `rest` is rounded to the column's precision
                    # above, so this comparison is exact rather than hopeful.
                    identifier=item.identifier if not rest else divide_item["identifier"],''', 1)

ast.parse(s)
assert s.count(GUARD) >= 3, "guard count %d" % s.count(GUARD)
assert "int(item.qty)" not in s, "the truncating arithmetic is still there"
if s != before:
    open(P, "w").write(s)
    print("divide_qty_fix: patched")
else:
    print("divide_qty_fix: already current")
