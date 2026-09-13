# The kitchen/bar board rendered nothing, with no console error.
#
# With group_items_by_order=1 the ticket loop calls
#     check_available_item(data, data)
# passing the ORDER payload as the "item". An order has no `item_group`, so
# include_item_group(undefined) is false (the centre lists 16 specific groups,
# not "All Item Groups") -> available=false -> add_order() never runs -> no
# ticket is appended and the board stays empty.
#
# The server already filters entries by item_group in get_command_filters, so
# this client-side re-check is redundant; simply don't apply it to a payload
# that carries no item_group. Item-level calls are unaffected. Idempotent.
p = "apps/restaurant_management/restaurant_management/public/restaurant/js/process-manage-class.js"
s = open(p).read()

MARK = "item.item_group === undefined"
if MARK in s:
    print("kitchen_board_group: already patched")
else:
    old = (
        "    return [\n"
        "      this.include_status(this.group_items_by_order ? order.status : item.status),\n"
        "      this.include_item_group(item.item_group),\n"
        "      this.item_available_in_branch(item),\n"
    )
    new = (
        "    return [\n"
        "      this.include_status(this.group_items_by_order ? order.status : item.status),\n"
        "      // a grouped ticket passes the order itself, which carries no item_group;\n"
        "      // the server already filtered the entries by group, so skip the re-check\n"
        "      (item.item_group === undefined || this.include_item_group(item.item_group)),\n"
        "      this.item_available_in_branch(item),\n"
    )
    assert s.count(old) == 1, "anchor count=%d" % s.count(old)
    open(p, "w").write(s.replace(old, new, 1))
    print("kitchen_board_group: patched")
