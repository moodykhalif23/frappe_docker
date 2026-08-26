"""Rename rooms and tables from their random hash to their readable description.

    echo 'exec(open("apps/restaurant_management/restaurant_management/rename_objects.py").read(), globals()); run()' \
      | docker compose exec -T backend bench --site <site> console

`run(dry=True)` prints the plan and changes nothing. Re-runnable: anything
already named after its description is skipped.
"""

import re

import frappe

# frappe rejects these in a docname, and a slash would break the desk route.
FORBIDDEN = re.compile(r'[<>;,"\'#/\\%?]')

MIRRORS = (
    ("tabOrder Entry Item", "room"),
    ("tabRestaurant Booking", "room"),
    ("tabRestaurant Permission", "room"),
)


def clean(description):
    name = FORBIDDEN.sub("", description or "").strip()
    name = re.sub(r"\s+", " ", name)
    return name


def plan():
    rows = []
    taken = set()
    for o in frappe.get_all("Restaurant Object", fields=["name", "description", "type"],
                            order_by="type asc, description asc"):
        target = clean(o.description)
        if not target or target == o.name:
            continue
        # description is unique, but a cleaned one could still collide.
        candidate, n = target, 1
        while candidate in taken or (candidate != o.name
                                     and frappe.db.exists("Restaurant Object", candidate)):
            n += 1
            candidate = "%s-%d" % (target, n)
        taken.add(candidate)
        rows.append((o.name, candidate, o.type))
    return rows


def run(dry=False):
    rows = plan()
    if not rows:
        print("nothing to rename — every object already carries its description")
        return []

    for old, new, kind in rows:
        print("%-12s %-14s -> %s" % (kind, old, new))
    if dry:
        print("\n%d object(s) would be renamed (dry run)" % len(rows))
        return rows

    renamed = []
    for old, new, _kind in rows:
        frappe.rename_doc("Restaurant Object", old, new, force=True, show_alert=False)
        renamed.append((old, new))

    # Link fields follow a rename; these columns are plain copies and do not.
    for table, column in MIRRORS:
        if not frappe.db.table_exists(table.replace("tab", "", 1)):
            continue
        for old, new in renamed:
            frappe.db.sql("update `%s` set `%s`=%%s where `%s`=%%s" % (table, column, column),
                          (new, old))

    frappe.db.commit()
    frappe.clear_cache()
    print("\nrenamed %d object(s)" % len(renamed))
    return renamed
