# Sale -> recipe -> issue, proven with real quantities on real stock.
#
#   exec(open(".../stock_test.py").read(), globals()); run()

import frappe

from restaurant_management import inventory as inv

ING_A = "ZZ Test Beef"
ING_B = "ZZ Test Oil"
DISH = "ZZ Test Steak"
PLAIN = "ZZ Test Uncosted Dish"


def _cleanup():
    for inum in frappe.get_all("POS Invoice", filters={"customer": ["like", "ZZ Test%"]}, pluck="name"):
        d = frappe.get_doc("POS Invoice", inum)
        if d.docstatus == 1:
            d.cancel()
        frappe.delete_doc("POS Invoice", inum, force=1, ignore_permissions=True)
    # Found by the items they move, not by remarks: the back-flush entry names the
    # sale, not the test. Newest first, or cancelling a receipt before the issues
    # it backed leaves them unbacked and the ledger refuses.
    touched = [r.parent for r in frappe.get_all(
        "Stock Entry Detail", filters={"item_code": ["like", "ZZ Test%"]},
        fields=["parent"], group_by="parent")]
    for se in frappe.get_all("Stock Entry", filters={"name": ["in", touched or [""]]},
                             pluck="name", order_by="creation desc"):
        d = frappe.get_doc("Stock Entry", se)
        if d.docstatus == 1:
            d.cancel()
        frappe.delete_doc("Stock Entry", se, force=1, ignore_permissions=True)
    for bom in frappe.get_all("BOM", filters={"item": DISH}, pluck="name"):
        d = frappe.get_doc("BOM", bom)
        if d.docstatus == 1:
            d.cancel()
        frappe.delete_doc("BOM", bom, force=1, ignore_permissions=True)
    for code in (ING_A, ING_B, DISH, PLAIN):
        if frappe.db.exists("Item", code):
            frappe.delete_doc("Item", code, force=1, ignore_permissions=True)
    for c in frappe.get_all("Customer", filters={"customer_name": ["like", "ZZ Test%"]}, pluck="name"):
        frappe.delete_doc("Customer", c, force=1, ignore_permissions=True)
    frappe.db.commit()


def _item(code, stock, uom="Kg", group=None):
    if frappe.db.exists("Item", code):
        return code
    frappe.get_doc({
        "doctype": "Item", "item_code": code, "item_name": code,
        "item_group": group or frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
        "stock_uom": uom, "is_stock_item": 1 if stock else 0,
        "include_item_in_manufacturing": 1 if stock else 0,
    }).insert(ignore_permissions=True)
    return code


def run():
    results = []

    def check(label, cond, detail=""):
        results.append((bool(cond), label, detail))

    _cleanup()
    inv.ensure_fields()
    store = inv._store()
    check("a store warehouse is resolved", store, str(store))

    _item(ING_A, True, "Kg")
    _item(ING_B, True, "Litre")
    _item(DISH, False, "Nos")
    _item(PLAIN, False, "Nos")

    # opening stock so there is something to burn
    receipt = frappe.get_doc({
        "doctype": "Stock Entry", "stock_entry_type": "Material Receipt",
        "company": inv._company(), "remarks": "ZZ Test opening",
        "items": [
            {"item_code": ING_A, "qty": 10, "t_warehouse": store, "basic_rate": 500},
            {"item_code": ING_B, "qty": 5, "t_warehouse": store, "basic_rate": 300},
        ],
    })
    receipt.insert(ignore_permissions=True)
    receipt.submit()

    def onhand(code):
        return frappe.db.get_value("Bin", {"item_code": code, "warehouse": store}, "actual_qty") or 0

    check("opening stock landed", onhand(ING_A) == 10 and onhand(ING_B) == 5,
          f"{onhand(ING_A)}kg / {onhand(ING_B)}L")

    # the recipe: one steak burns 0.25 kg beef and 0.02 L oil
    bom = frappe.get_doc({
        "doctype": "BOM", "item": DISH, "company": inv._company(),
        "quantity": 1, "is_active": 1, "is_default": 1, "with_operations": 0,
        "items": [
            {"item_code": ING_A, "qty": 0.25, "uom": "Kg", "rate": 500},
            {"item_code": ING_B, "qty": 0.02, "uom": "Litre", "rate": 300},
        ],
    })
    bom.insert(ignore_permissions=True)
    bom.submit()
    check("the recipe is found for the dish", inv._recipe(DISH) is not None)

    profile = frappe.db.get_value("POS Profile", {"disabled": 0}, "name")
    _ensure_shift(profile)
    cust = frappe.get_doc({
        "doctype": "Customer", "customer_name": "ZZ Test Diner",
        "customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}),
        "territory": frappe.db.get_value("Territory", {"is_group": 0}),
    }).insert(ignore_permissions=True)

    # four steaks and one dish that has no recipe at all
    sale = frappe.get_doc({
        "doctype": "POS Invoice", "customer": cust.name, "company": inv._company(),
        "pos_profile": profile, "set_warehouse": store, "update_stock": 0,
        "items": [
            {"item_code": DISH, "qty": 4, "rate": 1200, "warehouse": store},
            {"item_code": PLAIN, "qty": 2, "rate": 300, "warehouse": store},
        ],
        "payments": [{"mode_of_payment": frappe.db.get_value(
            "POS Payment Method", {"parent": profile}, "mode_of_payment") or "Cash",
            "amount": 5400}],
    })
    sale.insert(ignore_permissions=True)
    sale.submit()
    check("the sale is submitted", sale.docstatus == 1, sale.name)
    check("it is waiting to be back-flushed", sale.name in inv.pending_invoices())

    before_a, before_b = onhand(ING_A), onhand(ING_B)
    res = inv.backflush()
    check("back-flush issued an entry", res["issued"], str(res))
    check("it covered the sale", res["invoices"] >= 1, str(res["invoices"]))
    check("the dish with no recipe is reported, not silently dropped",
          PLAIN in res["uncosted"], str(res["uncosted"]))

    # 4 steaks x 0.25 kg = 1.0 kg, x 0.02 L = 0.08 L
    check("beef fell by exactly the recipe amount", round(before_a - onhand(ING_A), 3) == 1.0,
          f"{before_a} -> {onhand(ING_A)}")
    check("oil fell by exactly the recipe amount", round(before_b - onhand(ING_B), 3) == 0.08,
          f"{before_b} -> {onhand(ING_B)}")

    again = inv.backflush()
    check("running it twice does not double-issue", again["issued"] is None, str(again))
    check("and stock is unchanged", round(onhand(ING_A), 3) == round(before_a - 1.0, 3),
          str(onhand(ING_A)))

    # waste
    w_before = onhand(ING_A)
    waste = inv.record_waste(ING_A, 0.5, "ZZ Test spoiled in the walk-in")
    check("waste is issued", waste["entry"], waste["entry"])
    check("waste reduced the shelf", round(w_before - onhand(ING_A), 3) == 0.5,
          f"{w_before} -> {onhand(ING_A)}")
    try:
        inv.record_waste(ING_A, 1, "")
        check("waste demands a reason", False, "it accepted an empty reason")
    except Exception:
        check("waste demands a reason", True)

    # restock
    frappe.get_doc({"doctype": "Item Reorder", "parent": ING_A, "parenttype": "Item",
                    "parentfield": "reorder_levels", "warehouse": store,
                    "warehouse_reorder_level": 20, "warehouse_reorder_qty": 25,
                    "material_request_type": "Purchase"}).insert(ignore_permissions=True)
    frappe.db.commit()
    rows = {r["item_code"]: r for r in inv.restock_list(store)}
    check("the ingredient appears on the restock list", ING_A in rows, str(list(rows)[:4]))
    if ING_A in rows:
        check("it is flagged as needing a restock", rows[ING_A]["needs_restock"], str(rows[ING_A]))
        check("and it suggests a quantity", rows[ING_A]["suggested_order"] > 0,
              str(rows[ING_A]["suggested_order"]))

    # variance: everything that left was either recipe or waste
    today = frappe.utils.today()
    var = {r["item_code"]: r for r in inv.variance(today, today, store)}
    check("variance covers the ingredient", ING_A in var, str(list(var)[:4]))
    if ING_A in var:
        check("variance shows the 0.5 waste as the gap",
              round(var[ING_A]["difference"], 2) == 0.5, str(var[ING_A]))

    _cleanup()
    return _report(results)


def _ensure_shift(profile):
    """Billing needs an opening entry dated today; a stale one is refused."""
    today = frappe.utils.today()
    open_today = frappe.db.exists("POS Opening Entry", {
        "pos_profile": profile, "status": "Open", "docstatus": 1,
        "period_start_date": ["between", [today + " 00:00:00", today + " 23:59:59"]],
    })
    if open_today:
        return open_today
    for stale in frappe.get_all("POS Opening Entry",
                                filters={"pos_profile": profile, "status": "Open", "docstatus": 1},
                                pluck="name"):
        frappe.db.set_value("POS Opening Entry", stale, "status", "Closed", update_modified=False)
    frappe.db.commit()

    modes = frappe.get_all("POS Payment Method", filters={"parent": profile},
                           fields=["mode_of_payment"])
    doc = frappe.get_doc({
        "doctype": "POS Opening Entry",
        "company": inv._company(), "pos_profile": profile,
        "user": frappe.session.user, "period_start_date": frappe.utils.now_datetime(),
        "balance_details": [{"mode_of_payment": m.mode_of_payment, "opening_amount": 0}
                            for m in modes] or [{"mode_of_payment": "Cash", "opening_amount": 0}],
    })
    doc.insert(ignore_permissions=True)
    doc.submit()
    frappe.db.commit()
    return doc.name


def _report(results):
    failed = [r for r in results if not r[0]]
    for ok, label, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f"   [{detail}]" if detail else ""))
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    if failed:
        raise AssertionError(f"{len(failed)} stock checks failed")
    return "ok"
