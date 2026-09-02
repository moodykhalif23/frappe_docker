# Mirror the live station accounts, waiters and a second room onto a test site,
# so the multi-user drill runs here instead of in a client's books.
#
#   exec(open(".../mirror_stations.py").read(), globals()); run()

import frappe

ROLES = {
    "waiter@etham.co.ke": (["Restaurant User", "Waiter Station"], "Waiter Terminal"),
    "kitchen@etham.co.ke": (["Restaurant User", "Kitchen Station"], "Kitchen Screen"),
    "cashier@etham.co.ke": (["Restaurant User", "Restaurant Manager", "Accounts User",
                             "Sales Manager"], "Cashier Till"),
    "admin@etham.co.ke": (["Restaurant User", "Restaurant Manager", "Accounts User",
                           "Accounts Manager", "Sales Manager", "Sales User",
                           "Sales Master Manager", "Item Manager", "Stock Manager",
                           "Stock User", "Purchase Manager", "Purchase Master Manager",
                           "Manufacturing Manager", "Manufacturing User",
                           "HR Manager", "HR User", "System Manager", "Website Manager"], "Etham Admin"),
    "geff@etham.co.ke": (["Restaurant User", "Restaurant Manager", "Accounts User",
                          "Accounts Manager", "Sales Manager", "Sales User", "Item Manager",
                          "Stock Manager", "Stock User", "Manufacturing Manager",
                          "Manufacturing User", "Purchase Manager", "Purchase User",
                          "Purchase Master Manager", "HR User"], "Geff Manager"),
}
PASSWORDS = {
    "waiter@etham.co.ke": "Waiter", "kitchen@etham.co.ke": "Kitchen",
    "cashier@etham.co.ke": "Cashier", "admin@etham.co.ke": "Admin",
    "geff@etham.co.ke": "Geff",
}
WAITERS = [("Amina Test", "1111"), ("Moses Test", "2222"), ("Njeri Test", "3333")]
ROOM = "R 2"


def _style(x, y, z, w, h):
    return '{"x":"%s","y":"%s","z-index":"%s","width":"%spx","height":"%spx"}' % (x, y, z, w, h)


def run():
    frappe.set_user("Administrator")
    out = []

    for email, (roles, full) in ROLES.items():
        if frappe.db.exists("User", email):
            u = frappe.get_doc("User", email)
        else:
            first, last = full.split(" ", 1)
            u = frappe.get_doc({"doctype": "User", "email": email, "first_name": first,
                                "last_name": last, "send_welcome_email": 0,
                                "user_type": "System User"})
            u.insert(ignore_permissions=True)
            out.append("created " + email)
        have = {r.role for r in u.roles}
        for r in roles:
            if r not in have and frappe.db.exists("Role", r):
                u.append("roles", {"role": r})
        u.new_password = PASSWORDS[email] + "@2026"
        u.enabled = 1
        u.flags.ignore_permissions = True
        u.save(ignore_permissions=True)

    for name, pin in WAITERS:
        if frappe.db.exists("Restaurant Waiter", name):
            w = frappe.get_doc("Restaurant Waiter", name)
        else:
            w = frappe.get_doc({"doctype": "Restaurant Waiter", "waiter_name": name, "pin": pin})
            w.insert(ignore_permissions=True)
            out.append("waiter " + name)
        w.pin = pin
        w.active = 1
        w.flags.ignore_permissions = True
        w.save(ignore_permissions=True)

    company = frappe.defaults.get_user_default("Company")
    if not frappe.db.exists("Restaurant Object", ROOM):
        r = frappe.get_doc({"doctype": "Restaurant Object", "type": "Room",
                            "description": ROOM, "company": company})
        r.flags.ignore_permissions = True
        r.insert(ignore_permissions=True)
        if r.name != ROOM:
            frappe.rename_doc("Restaurant Object", r.name, ROOM, force=True)
        out.append("room " + ROOM)

    have = frappe.get_all("Restaurant Object", filters={"type": "Table", "room": ROOM}, pluck="name")
    nums = [int(t.split()[-1]) for t in frappe.get_all("Restaurant Object",
            filters={"type": "Table"}, pluck="description") if t and t.split()[-1].isdigit()]
    nxt = max(nums or [0]) + 1
    colors = ["#1a4469", "#2e844e", "#97264f", "#505a62"]
    for i in range(max(0, 4 - len(have))):
        desc = "Table %d" % (nxt + i)
        d = frappe.get_doc({"doctype": "Restaurant Object", "type": "Table", "room": ROOM,
                            "description": desc, "no_of_seats": 4, "shape": "Square",
                            "color": colors[i % 4], "company": company,
                            "data_style": _style(60 + (i % 3) * 260, 90 + (i // 3) * 220,
                                                 60 + i, 200, 130)})
        d.flags.ignore_permissions = True
        d.insert(ignore_permissions=True)
        if d.name != desc and not frappe.db.exists("Restaurant Object", desc):
            frappe.rename_doc("Restaurant Object", d.name, desc, force=True)
        out.append("table " + desc)

    frappe.db.commit()
    print("MIRROR " + ("; ".join(out) if out else "nothing to add"))
    print("MIRROR r2 tables: %s" % frappe.get_all(
        "Restaurant Object", filters={"type": "Table", "room": ROOM}, pluck="name"))
