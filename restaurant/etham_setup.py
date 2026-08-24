"""Stand Etham Eatery up on a site that currently holds demo data.

Order matters. Etham is built alongside the demo, the floor and POS are moved
onto it and verified, and only then is the demo wiped — so there is always a
working state to fall back to. Every phase is idempotent.

    exec(open(".../etham_setup.py").read(), globals())
    create_company(); load_menu(); move_floor(); make_profile()
    status()                      # check before the destructive step
    wipe_demo()                   # once you are happy

Logo: put the PNG at /tmp/etham-logo.png in the backend container first.
"""

import os

import frappe

COMPANY = "Etham Eatery"
ABBR = "ETH"
CURRENCY = "KES"
COUNTRY = "Kenya"
LOGO_PATH = os.environ.get("ETHAM_LOGO", "/tmp/etham-logo.png")

_here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else "/tmp"
try:
    from restaurant_management.etham_menu import BAR_CATEGORIES, MENU
except Exception:
    _menu_py = os.environ.get("ETHAM_MENU", "/tmp/etham_menu.py")
    _ns = {}
    exec(open(_menu_py).read(), _ns)
    MENU, BAR_CATEGORIES = _ns["MENU"], _ns["BAR_CATEGORIES"]

CATEGORIES = []
for _row in MENU:
    if _row[0] not in CATEGORIES:
        CATEGORIES.append(_row[0])


# ---------------- phase 1: the company ----------------

def create_company():
    if frappe.db.exists("Company", COMPANY):
        print("COMPANY exists:", COMPANY)
    else:
        doc = frappe.get_doc({
            "doctype": "Company", "company_name": COMPANY, "abbr": ABBR,
            "default_currency": CURRENCY, "country": COUNTRY,
            "create_chart_of_accounts_based_on": "Standard Template",
            "chart_of_accounts": "Standard",
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        print("COMPANY created:", doc.name)
    _set_logo()
    _letter_head()
    return COMPANY


def _upload(path, name):
    if not os.path.exists(path):
        print("LOGO missing at", path, "- skipping")
        return None
    existing = frappe.db.get_value("File", {"file_name": name}, "file_url")
    if existing:
        return existing
    with open(path, "rb") as fh:
        doc = frappe.get_doc({
            "doctype": "File", "file_name": name, "is_private": 0,
            "content": fh.read(), "decode": False,
        }).insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.file_url


def _set_logo():
    url = _upload(LOGO_PATH, "etham-logo.png")
    if not url:
        return
    frappe.db.set_value("Company", COMPANY, "company_logo", url)
    # Same mark on the desk and the browser tab.
    for key, val in (("app_logo_url", url), ("banner_image", url)):
        try:
            frappe.db.set_single_value("Website Settings", key, url)
        except Exception:
            pass
    frappe.db.commit()
    print("LOGO set:", url)


def _letter_head():
    """Invoices, receipts and quotes all print through this."""
    url = frappe.db.get_value("Company", COMPANY, "company_logo")
    if not url:
        return
    html = (
        '<div style="display:flex;align-items:center;gap:14px;padding:6px 0 10px;'
        'border-bottom:2px solid #6f5844;">'
        f'<img src="{url}" style="height:64px;width:auto" alt="Etham Eatery">'
        '<div style="font-family:Georgia,serif;line-height:1.3">'
        '<div style="font-size:20px;font-weight:700;color:#2b2118">Etham Eatery</div>'
        '<div style="font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#8a7a68">'
        'All prices in Kenya Shillings</div></div></div>'
    )
    if frappe.db.exists("Letter Head", COMPANY):
        lh = frappe.get_doc("Letter Head", COMPANY)
        lh.content = html
        lh.source = "HTML"
        lh.is_default = 1
        lh.save(ignore_permissions=True)
    else:
        frappe.get_doc({
            "doctype": "Letter Head", "letter_head_name": COMPANY,
            "source": "HTML", "content": html, "is_default": 1, "disabled": 0,
        }).insert(ignore_permissions=True)
    frappe.db.commit()
    print("LETTER HEAD set")


# ---------------- phase 2: the menu ----------------

def _group(name):
    if frappe.db.exists("Item Group", name):
        return name
    parent = frappe.db.get_value("Item Group", {"is_group": 1, "parent_item_group": ""}) or "All Item Groups"
    frappe.get_doc({
        "doctype": "Item Group", "item_group_name": name,
        "parent_item_group": parent, "is_group": 0,
    }).insert(ignore_permissions=True)
    return name


def _price_list():
    return (frappe.db.get_value("Price List", {"enabled": 1, "selling": 1, "currency": CURRENCY})
            or frappe.db.get_value("Price List", {"enabled": 1, "selling": 1}))


def _item(name, group, description, rate, veg):
    if not frappe.db.exists("Item", name):
        frappe.get_doc({
            "doctype": "Item", "item_code": name, "item_name": name,
            "item_group": group, "stock_uom": "Nos",
            "is_stock_item": 0, "is_sales_item": 1, "is_purchase_item": 0,
            "description": description,
            "include_item_in_manufacturing": 0,
        }).insert(ignore_permissions=True)
    # An empty description must stay empty — the card repeats it under the name.
    frappe.db.set_value("Item", name, {"item_type": veg, "item_group": group,
                                       "description": description},
                        update_modified=False)
    pl = _price_list()
    existing = frappe.db.get_value("Item Price", {"item_code": name, "price_list": pl}, "name")
    if existing:
        frappe.db.set_value("Item Price", existing, "price_list_rate", rate)
    else:
        frappe.get_doc({
            "doctype": "Item Price", "item_code": name, "price_list": pl,
            "price_list_rate": rate, "currency": CURRENCY, "selling": 1,
        }).insert(ignore_permissions=True)
    return name


def _menu():
    """The Restaurant Menu holding our items.

    The doctype hash-names itself, so a chosen name is silently discarded — never
    look it up or store it by a name you picked.
    """
    probe = MENU[0][1]
    for name in frappe.get_all("Restaurant Menu", pluck="name"):
        if frappe.db.exists("Restaurant Menu Item", {"parent": name, "item": probe}):
            return name
    doc = frappe.new_doc("Restaurant Menu")
    doc.company = COMPANY
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.name


def load_menu():
    for cat in CATEGORIES:
        _group(cat)
    for cat, name, desc, rate, veg in MENU:
        _item(name, cat, desc, rate, veg)
    frappe.db.commit()

    menu = frappe.get_doc("Restaurant Menu", _menu())
    field = next(f.fieldname for f in frappe.get_meta("Restaurant Menu").get_table_fields()
                 if f.options == "Restaurant Menu Item")
    have = {r.item for r in menu.get(field)}
    for cat, item, _d, _r, _v in MENU:
        if item not in have:
            menu.append(field, {"item": item, "item_group": cat, "status": 1})
    menu.save(ignore_permissions=True)
    frappe.db.commit()
    print("MENU %s: %s items, %s rows" % (menu.name, len(MENU), len(menu.get(field))))
    return menu.name


def route_production_centres():
    """Drinks to the Bar, everything else to the Kitchen."""
    bar = [c for c in CATEGORIES if c in BAR_CATEGORIES]
    kitchen = [c for c in CATEGORIES if c not in BAR_CATEGORIES]
    for label, groups in (("Kitchen", kitchen), ("Bar", bar)):
        pc = frappe.db.get_value("Restaurant Object", {"type": "Production Center",
                                                       "description": label}, "name")
        if not pc:
            print("PC %s not found — skipping" % label)
            continue
        doc = frappe.get_doc("Restaurant Object", pc)
        doc.set("production_center_group", [])
        for g in groups:
            doc.append("production_center_group", {"item_group": g})
        doc.save(ignore_permissions=True)
        print("PC %s routes %s categories" % (label, len(groups)))
    frappe.db.commit()


# ---------------- phase 3: floor and POS ----------------

def move_floor():
    """Repoint the existing rooms, tables and production centres at Etham."""
    n = frappe.db.sql("update `tabRestaurant Object` set company=%s", COMPANY)
    frappe.db.commit()
    counts = frappe.db.sql("""select type, count(*) from `tabRestaurant Object` group by type""")
    print("FLOOR moved to %s: %s" % (COMPANY, dict(counts)))


def _walkin():
    name = "Walk-in Guest"
    if not frappe.db.exists("Customer", name):
        frappe.get_doc({
            "doctype": "Customer", "customer_name": name,
            "customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}),
            "territory": frappe.db.get_value("Territory", {"is_group": 0}),
        }).insert(ignore_permissions=True)
    return name


def _payment_accounts(modes):
    """Every Mode of Payment needs an account per company or the POS Profile refuses."""
    cash = (frappe.db.get_value("Company", COMPANY, "default_cash_account")
            or frappe.db.get_value("Account", {"company": COMPANY, "account_type": "Cash", "is_group": 0}))
    bank_parent = frappe.db.get_value("Account", {"company": COMPANY, "account_type": "Bank", "is_group": 1})

    for mode in modes:
        doc = frappe.get_doc("Mode of Payment", mode)
        if any(a.company == COMPANY for a in doc.accounts):
            continue
        account = cash
        if mode != "Cash" and bank_parent:
            ledger = "%s - %s" % (mode, ABBR)
            if not frappe.db.exists("Account", ledger):
                frappe.get_doc({
                    "doctype": "Account", "account_name": mode, "company": COMPANY,
                    "parent_account": bank_parent, "account_type": "Bank", "is_group": 0,
                    "account_currency": CURRENCY,
                }).insert(ignore_permissions=True)
            account = ledger
        doc.append("accounts", {"company": COMPANY, "default_account": account})
        doc.save(ignore_permissions=True)
        print("  %s -> %s" % (mode, account))
    frappe.db.commit()


def make_profile(name="Etham"):
    warehouse = (frappe.db.get_value("Warehouse", {"company": COMPANY, "is_group": 0,
                                                   "warehouse_name": "Stores"})
                 or frappe.db.get_value("Warehouse", {"company": COMPANY, "is_group": 0}))
    modes = [m for m in ("Cash", "M-Pesa") if frappe.db.exists("Mode of Payment", m)]
    if not modes:
        modes = ["Cash"]
    _payment_accounts(modes)

    if frappe.db.exists("POS Profile", name):
        prof = frappe.get_doc("POS Profile", name)
    else:
        prof = frappe.new_doc("POS Profile")
        prof.name = name
    prof.update({
        "company": COMPANY, "warehouse": warehouse, "currency": CURRENCY,
        "update_stock": 0, "customer": _walkin(),
        "selling_price_list": _price_list(),
        "write_off_account": frappe.db.get_value("Company", COMPANY, "write_off_account")
            or frappe.db.get_value("Account", {"company": COMPANY, "account_name": "Write Off"}),
        "write_off_cost_center": frappe.db.get_value("Company", COMPANY, "cost_center")
            or frappe.db.get_value("Cost Center", {"company": COMPANY, "is_group": 0}),
        "disabled": 0,
        "restaurant_menu": _menu(),
    })
    prof.set("payments", [{"mode_of_payment": m, "default": 1 if i == 0 else 0}
                          for i, m in enumerate(modes)])
    prof.save(ignore_permissions=True) if prof.get("name") and frappe.db.exists("POS Profile", name) \
        else prof.insert(ignore_permissions=True)
    frappe.db.commit()
    print("POS PROFILE %s -> %s (%s, menu %s)" % (prof.name, COMPANY, ",".join(modes), _menu()))
    return prof.name


def open_shift(profile=None, opening=5000):
    profile = profile or frappe.db.get_value("POS Profile", {"company": COMPANY, "disabled": 0})
    for oe in frappe.get_all("POS Opening Entry",
                             filters={"status": "Open", "pos_profile": profile}, fields=["name"]):
        print("SHIFT already open on %s: %s" % (profile, oe.name))
        return oe.name
    prof = frappe.get_doc("POS Profile", profile)
    doc = frappe.get_doc({
        "doctype": "POS Opening Entry", "company": COMPANY, "pos_profile": profile,
        "user": frappe.session.user, "period_start_date": frappe.utils.now_datetime(),
        "posting_date": frappe.utils.today(),
        "balance_details": [{"mode_of_payment": p.mode_of_payment,
                             "opening_amount": opening if p.mode_of_payment == "Cash" else 0}
                            for p in prof.payments],
    })
    doc.insert(ignore_permissions=True)
    doc.submit()
    frappe.db.commit()
    print("SHIFT opened:", doc.name)
    return doc.name


def setup():
    create_company(); load_menu(); route_production_centres()
    move_floor(); make_profile(); open_shift()
    status()


# ---------------- phase 4: retire the demo ----------------

def _nuke(doctype, filters=None):
    """Cancel then delete. Submitted docs refuse deletion outright."""
    kept = 0
    for name in frappe.get_all(doctype, filters=filters or {}, pluck="name"):
        try:
            doc = frappe.get_doc(doctype, name)
            if doc.meta.is_submittable and doc.docstatus == 1:
                doc.flags.ignore_links = True
                doc.flags.ignore_permissions = True
                doc.cancel()
            frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
        except Exception as exc:
            kept += 1
            print("  kept %s %s (%s)" % (doctype, name, str(exc)[:70]))
    frappe.db.commit()
    return kept


def wipe_demo(company=None):
    """Remove the demo trading data, then the demo company itself."""
    demo = company or next((c for c in frappe.get_all("Company", pluck="name") if c != COMPANY), None)
    if not demo:
        print("WIPE: no other company found")
        return
    print("WIPE target:", demo)

    keep_items = {row[1] for row in MENU}
    for dt in ("Table Order", "Restaurant Booking"):
        _nuke(dt)
    print("  orders and bookings cleared")

    for dt in ("POS Invoice Merge Log", "POS Invoice", "Sales Invoice", "Payment Entry",
               "Stock Entry", "POS Closing Entry", "POS Opening Entry"):
        if frappe.db.exists("DocType", dt):
            _nuke(dt, {"company": demo})
    print("  demo vouchers cleared")

    for c in frappe.get_all("Customer", pluck="name"):
        if c == "Walk-in Guest":
            continue
        try:
            frappe.delete_doc("Customer", c, force=True, ignore_permissions=True)
        except Exception as e:
            print("  kept customer %s (%s)" % (c, str(e)[:50]))

    for it in frappe.get_all("Item", pluck="name"):
        if it in keep_items:
            continue
        try:
            frappe.delete_doc("Item", it, force=True, ignore_permissions=True)
        except Exception as e:
            print("  kept item %s (%s)" % (it, str(e)[:50]))

    ours = _menu()
    for m in frappe.get_all("Restaurant Menu", pluck="name"):
        if m != ours:
            frappe.delete_doc("Restaurant Menu", m, force=True, ignore_permissions=True)
    for w in frappe.get_all("Restaurant Waiter", pluck="name"):
        frappe.delete_doc("Restaurant Waiter", w, force=True, ignore_permissions=True)
    frappe.db.commit()
    print("  demo customers, items, menus and waiters cleared")

    frappe.defaults.set_global_default("company", COMPANY)
    for prof in frappe.get_all("POS Profile", filters={"company": demo}, pluck="name"):
        frappe.delete_doc("POS Profile", prof, force=True, ignore_permissions=True)
    frappe.db.commit()

    try:
        frappe.delete_doc("Company", demo, force=True, ignore_permissions=True)
        frappe.db.commit()
        print("WIPE: company %s deleted" % demo)
    except Exception as e:
        print("WIPE: company %s kept — %s" % (demo, str(e)[:160]))
    status()


def status():
    print("")
    print("STATUS")
    print("  companies      :", frappe.get_all("Company", pluck="name"))
    print("  default company:", frappe.defaults.get_global_default("company"))
    print("  logo           :", frappe.db.get_value("Company", COMPANY, "company_logo"))
    print("  letter head    :", frappe.db.exists("Letter Head", COMPANY))
    print("  menu rows      :", frappe.db.count("Restaurant Menu Item"))
    print("  items          :", frappe.db.count("Item"))
    print("  item groups    :", frappe.db.count("Item Group"))
    print("  rooms / tables :", frappe.db.count("Restaurant Object", {"type": "Room"}),
          "/", frappe.db.count("Restaurant Object", {"type": "Table"}))
    print("  pos profiles   :", frappe.get_all("POS Profile", fields=["name", "company", "restaurant_menu"]))
    print("  open shift     :", frappe.get_all("POS Opening Entry", filters={"status": "Open"},
                                               fields=["name", "pos_profile"]))
    print("  customers      :", frappe.db.count("Customer"), "| waiters:", frappe.db.count("Restaurant Waiter"))
    print("  orders         :", frappe.db.count("Table Order"), "| bookings:", frappe.db.count("Restaurant Booking"))

def activate():
    """Point the session at Etham without deleting anything.

    move_floor() repoints the rooms and tables at Etham, so until the default
    company and the active profile follow, the floor filters to nothing.
    """
    frappe.defaults.set_global_default("company", COMPANY)
    for prof in frappe.get_all("POS Profile", filters={"company": ["!=", COMPANY]}, pluck="name"):
        frappe.db.set_value("POS Profile", prof, "disabled", 1)
        print("  disabled old profile:", prof)
    frappe.db.commit()
    ours = frappe.db.get_value("POS Profile", {"company": COMPANY, "disabled": 0})
    open_shift(ours)
    frappe.clear_cache()
    print("ACTIVE company=%s profile=%s" % (COMPANY, ours))
    status()
