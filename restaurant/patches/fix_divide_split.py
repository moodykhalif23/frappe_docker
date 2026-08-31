# Splitting a check crashed twice over: divide() builds the moved item without
# the customization fields update_item() reads with hard brackets, and the
# raw-SQL update chokes on any non-string value, so a partial split died too.
P = "apps/restaurant_management/restaurant_management/restaurant_management/doctype/table_order/table_order.py"

src = open(P).read()
changed = False

if "sub_items=item.sub_items" not in src:
    OLD_DIVIDE = '''                    identifier=item.identifier if rest == 0 else divide_item["identifier"],
                    notes=item.notes,'''
    NEW_DIVIDE = '''                    identifier=item.identifier if rest == 0 else divide_item["identifier"],
                    notes=item.notes,
                    sub_items=item.sub_items,
                    is_customizable=item.is_customizable,'''
    if OLD_DIVIDE not in src:
        raise SystemExit("divide split: divide() anchor not found")
    src = src.replace(OLD_DIVIDE, NEW_DIVIDE, 1)
    changed = True

if 'entry.get("sub_items")' not in src:
    OLD_ITEM = '''                sub_items=entry["sub_items"],
                is_customizable=entry["is_customizable"],'''
    NEW_ITEM = '''                sub_items=entry.get("sub_items"),
                is_customizable=entry.get("is_customizable") or 0,'''
    if OLD_ITEM not in src:
        raise SystemExit("divide split: update_item anchor not found")
    src = src.replace(OLD_ITEM, NEW_ITEM, 1)
    changed = True

if 'frappe.db.set_value("Order Entry Item", row, data' not in src:
    lines = src.split("\n")
    start = next((i for i, l in enumerate(lines) if "values = ','.join" in l), None)
    end = next((i for i, l in enumerate(lines)
                if i > (start or 0) and 'return "db_commit"' in l), None)
    if start is None or end is None:
        raise SystemExit("divide split: update_item SQL block not found")
    lines[start:end + 1] = [
        '                row = frappe.db.get_value("Order Entry Item", {"identifier": entry["identifier"]}, "name")',
        '                frappe.db.set_value("Order Entry Item", row, data, update_modified=False)',
        '',
        '                return "db_commit"',
    ]
    src = "\n".join(lines)
    changed = True

if changed:
    open(P, "w").write(src)
    print("divide split: whole and partial splits both survive")
else:
    print("divide split: already applied")
