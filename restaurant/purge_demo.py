# Remove what an earlier demo company left behind. Its Company record was
# deleted but its ledger, warehouses, accounts and cost centres were not, so the
# books still carry a restaurant that does not exist.
#
#   exec(open(".../purge_demo.py").read(), globals()); report()   # look first
#   exec(open(".../purge_demo.py").read(), globals()); purge("TD") # then act

import frappe


def _suffix(abbr):
    return "%- " + abbr


def _count(doctype, abbr):
    try:
        return frappe.db.sql(
            "select count(*) from `tab{0}` where name like %s".format(doctype),
            (_suffix(abbr),))[0][0]
    except Exception:
        return 0


def report(abbr="TD"):
    """What a purge would remove, and what it would leave alone."""
    live = [c.name for c in frappe.get_all("Company", fields=["name", "abbr"])
            if c.name]
    print("companies that exist:", live)
    rows = {
        "Stock Ledger Entry": frappe.db.sql(
            "select count(*) from `tabStock Ledger Entry` where warehouse like %s",
            (_suffix(abbr),))[0][0],
        "Bin": frappe.db.sql(
            "select count(*) from `tabBin` where warehouse like %s", (_suffix(abbr),))[0][0],
        "GL Entry": frappe.db.sql(
            "select count(*) from `tabGL Entry` where account like %s", (_suffix(abbr),))[0][0],
        "Warehouse": _count("Warehouse", abbr),
        "Cost Center": _count("Cost Center", abbr),
        "Account": _count("Account", abbr),
    }
    for k, v in rows.items():
        print(f"  {k}: {v}")
    return rows


def purge(abbr="TD"):
    """Delete the orphans of a company that no longer exists.

    Refuses while a company still uses the abbreviation — that would be
    deleting a live restaurant's books, not a demo's.
    """
    for c in frappe.get_all("Company", fields=["name", "abbr"]):
        if (c.abbr or "").strip().upper() == abbr.strip().upper():
            frappe.throw("Company {0} still uses {1} — refusing".format(c.name, abbr))

    like = _suffix(abbr)
    removed = {}

    # Ledgers first: they reference the masters below.
    for table, col in (("Stock Ledger Entry", "warehouse"), ("GL Entry", "account"),
                       ("Bin", "warehouse")):
        n = frappe.db.sql("select count(*) from `tab{0}` where {1} like %s".format(table, col),
                          (like,))[0][0]
        frappe.db.sql("delete from `tab{0}` where {1} like %s".format(table, col), (like,))
        removed[table] = n

    # Then the masters, children before parents.
    for doctype in ("Warehouse", "Cost Center", "Account"):
        names = frappe.db.sql_list(
            "select name from `tab{0}` where name like %s order by lft desc".format(doctype)
            if frappe.db.has_column(doctype, "lft")
            else "select name from `tab{0}` where name like %s".format(doctype), (like,))
        gone = 0
        for name in names:
            try:
                frappe.delete_doc(doctype, name, force=1, ignore_permissions=True,
                                  ignore_on_trash=True, delete_permanently=True)
                gone += 1
            except Exception as e:
                print("  kept {0} {1}: {2}".format(doctype, name, str(e)[:70]))
        removed[doctype] = gone

    frappe.db.commit()
    print("removed:", removed)
    return removed
