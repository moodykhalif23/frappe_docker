# The pad's boot call returns one item-group entry per menu row, undeduplicated,
# and the client sends that whole list back as a GET filter. At 170 dishes the
# request line exceeds nginx's 4094-byte limit and the items panel 400s, so a
# real menu breaks the pad while a small demo one does not.
P = "apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_settings/restaurant_settings.py"

src = open(P).read()
if "sorted({item.item_group" in src:
    print("dedupe item groups: already applied")
    raise SystemExit

OLD = """          parent_item_groups = frappe.get_all("Item Group", "parent_item_group",
            filters=dict(name=("in", [item.item_group for item in groups_of_items]))
          )

          items_groups = [item.item_group for item in groups_of_items] + [item.parent_item_group for item in parent_item_groups]"""

NEW = """          parent_item_groups = frappe.get_all("Item Group", "parent_item_group",
            filters=dict(name=("in", sorted({item.item_group for item in groups_of_items})))
          )

          items_groups = sorted({item.item_group for item in groups_of_items}
                                | {item.parent_item_group for item in parent_item_groups if item.parent_item_group})"""

if OLD not in src:
    raise SystemExit("dedupe item groups: anchor not found - restaurant_settings.py changed upstream")

open(P, "w").write(src.replace(OLD, NEW, 1))
print("dedupe item groups: applied")
