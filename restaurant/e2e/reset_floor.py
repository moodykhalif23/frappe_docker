# Hard floor reset for a TEST site: cancel every open check, close every party,
# clear every tile. Refuses to run unless the site name looks local.
#
#   exec(open(".../reset_floor.py").read(), globals()); run()

import frappe


def run(force=False):
    site = frappe.local.site
    if not force and not (site.endswith(".localhost") or site.startswith("test")):
        print("REFUSING: %s does not look like a test site (pass force=True)" % site)
        return
    frappe.set_user("Administrator")
    counts = {"orders": 0, "parties": 0, "tables": 0}

    for o in frappe.get_all("Table Order", filters={"status": ["not in", ["Invoiced", "Cancelled"]]},
                            fields=["name", "docstatus"]):
        frappe.db.set_value("Table Order", o.name, "status", "Cancelled", update_modified=False)
        counts["orders"] += 1

    for b in frappe.get_all("Restaurant Booking", filters={"status": "Open"}, pluck="name"):
        frappe.db.set_value("Restaurant Booking", b, "status", "Closed", update_modified=False)
        counts["parties"] += 1

    for tbl in frappe.get_all("Restaurant Object", filters={"type": "Table"}, pluck="name"):
        frappe.db.set_value("Restaurant Object", tbl,
                            {"customer": None, "current_user": None, "waiter": None},
                            update_modified=False)
        counts["tables"] += 1

    frappe.db.commit()
    print("RESET " + str(counts))
