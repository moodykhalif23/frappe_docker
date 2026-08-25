# What the kitchen actually burns: a sale, its recipe, and the stock that leaves.
# COPY'd whole into the app, so a rebake always lands the current version.

import frappe

BACKFLUSH_FIELD = "restaurant_backflushed"


def _company():
    return (frappe.defaults.get_global_default("company")
            or frappe.db.get_value("Company", {}, "name"))


def _store(pos_profile=None):
    """The warehouse the floor sells out of."""
    if pos_profile:
        wh = frappe.db.get_value("POS Profile", pos_profile, "warehouse")
        if wh:
            return wh
    wh = frappe.db.get_value("POS Profile", {"disabled": 0}, "warehouse")
    return wh or frappe.db.get_value("Warehouse", {"company": _company(), "is_group": 0}, "name")


def ensure_fields():
    """Idempotent: marks an invoice once its ingredients have been issued."""
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    create_custom_fields({
        "POS Invoice": [{
            "fieldname": BACKFLUSH_FIELD, "fieldtype": "Check", "label": "Stock Consumed",
            "read_only": 1, "insert_after": "status", "no_copy": 1,
        }],
    }, ignore_validate=True)
    frappe.db.commit()
    return "ok"


def _recipe(item_code):
    """The active default BOM for a dish, with the batch size it yields."""
    row = frappe.db.get_value(
        "BOM", {"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1},
        ["name", "quantity"], as_dict=True)
    if not row:
        row = frappe.db.get_value(
            "BOM", {"item": item_code, "is_active": 1, "docstatus": 1},
            ["name", "quantity"], as_dict=True)
    return row


def _needs(invoices):
    """Ingredients owed by these invoices, and the dishes that have no recipe.

    Components are issued as the recipe lists them: a prepped sub-item that is
    stocked was produced by its own entry, so exploding it would double-count.
    """
    need, uncosted = {}, {}
    for inv in invoices:
        for it in frappe.get_all("POS Invoice Item", filters={"parent": inv},
                                 fields=["item_code", "qty"]):
            bom = _recipe(it.item_code)
            if not bom:
                uncosted[it.item_code] = uncosted.get(it.item_code, 0) + (it.qty or 0)
                continue
            batch = bom.quantity or 1
            for c in frappe.get_all("BOM Item", filters={"parent": bom.name},
                                    fields=["item_code", "qty", "uom"]):
                if not frappe.db.get_value("Item", c.item_code, "is_stock_item"):
                    continue
                per_dish = (c.qty or 0) / batch
                key = (c.item_code, c.uom)
                need[key] = need.get(key, 0) + per_dish * (it.qty or 0)
    return need, uncosted


@frappe.whitelist()
def pending_invoices(day=None):
    """Submitted sales whose ingredients have not been issued yet."""
    if not frappe.db.has_column("POS Invoice", BACKFLUSH_FIELD):
        ensure_fields()
    filters = {"docstatus": 1, BACKFLUSH_FIELD: 0}
    if day:
        filters["posting_date"] = day
    return frappe.get_all("POS Invoice", filters=filters, pluck="name", order_by="creation")


@frappe.whitelist()
def backflush(day=None, pos_profile=None):
    """Issue the ingredients behind every sale not yet accounted for.

    One entry per run, marked on each invoice it covers, so running twice does
    not double-issue.
    """
    invoices = pending_invoices(day)
    if not invoices:
        return {"issued": None, "invoices": 0, "lines": 0, "uncosted": {}}

    need, uncosted = _needs(invoices)
    if not need:
        for inv in invoices:
            frappe.db.set_value("POS Invoice", inv, BACKFLUSH_FIELD, 1, update_modified=False)
        frappe.db.commit()
        return {"issued": None, "invoices": len(invoices), "lines": 0, "uncosted": uncosted}

    store = _store(pos_profile)
    entry = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Issue",
        "company": _company(),
        "remarks": "Kitchen consumption for {0} sale(s)".format(len(invoices)),
        "items": [{"item_code": code, "qty": round(qty, 4), "uom": uom, "s_warehouse": store}
                  for (code, uom), qty in sorted(need.items()) if qty > 0],
    })
    entry.insert(ignore_permissions=True)
    entry.submit()

    for inv in invoices:
        frappe.db.set_value("POS Invoice", inv, BACKFLUSH_FIELD, 1, update_modified=False)
    frappe.db.commit()
    return {"issued": entry.name, "invoices": len(invoices),
            "lines": len(entry.items), "uncosted": uncosted}


@frappe.whitelist()
def record_waste(item_code, qty, reason, warehouse=None):
    """Spoilage, breakage, staff meals — a loss with a name on it."""
    qty = float(qty or 0)
    if qty <= 0:
        frappe.throw(frappe._("How much was lost?"))
    if not (reason or "").strip():
        frappe.throw(frappe._("Say what happened — an unexplained loss is a guess"))

    entry = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Issue",
        "company": _company(),
        "remarks": "Waste: {0}".format(reason.strip()),
        "items": [{"item_code": item_code, "qty": qty,
                   "s_warehouse": warehouse or _store()}],
    })
    entry.insert(ignore_permissions=True)
    entry.submit()
    frappe.db.commit()
    return {"entry": entry.name, "item": item_code, "qty": qty, "reason": reason.strip()}


@frappe.whitelist()
def restock_list(warehouse=None):
    """What to buy: on hand against the level it should not fall below."""
    store = warehouse or _store()
    rows = []
    for b in frappe.get_all("Bin", filters={"warehouse": store},
                            fields=["item_code", "actual_qty", "ordered_qty",
                                    "reserved_qty", "projected_qty", "stock_uom"]):
        item = frappe.db.get_value("Item", b.item_code,
                                   ["item_name", "is_stock_item"], as_dict=True)
        if not item or not item.is_stock_item:
            continue
        rule = frappe.db.get_value(
            "Item Reorder", {"parent": b.item_code, "warehouse": store},
            ["warehouse_reorder_level", "warehouse_reorder_qty"], as_dict=True)
        level = (rule.warehouse_reorder_level if rule else 0) or 0
        short = level - (b.projected_qty or 0)
        rows.append({
            "item_code": b.item_code,
            "item_name": item.item_name or b.item_code,
            "uom": b.stock_uom,
            "on_hand": b.actual_qty or 0,
            "on_order": b.ordered_qty or 0,
            "projected": b.projected_qty or 0,
            "reorder_level": level,
            "suggested_order": round(max(short, 0) or
                                     ((rule.warehouse_reorder_qty if rule else 0) or 0), 3)
            if short > 0 else 0,
            "needs_restock": bool(short > 0) or (b.actual_qty or 0) <= 0,
        })
    rows.sort(key=lambda r: (not r["needs_restock"], -(r["reorder_level"] - r["projected"])))
    return rows


@frappe.whitelist()
def variance(from_date, to_date, warehouse=None):
    """What the recipes say was used, against what actually left the shelf."""
    store = warehouse or _store()
    invoices = frappe.get_all(
        "POS Invoice",
        filters={"docstatus": 1, "posting_date": ["between", [from_date, to_date]]},
        pluck="name")
    theoretical, _ = _needs(invoices)
    theory = {}
    for (code, _uom), qty in theoretical.items():
        theory[code] = theory.get(code, 0) + qty

    actual = {}
    for r in frappe.db.sql("""
        select sle.item_code, -sum(sle.actual_qty) as qty
        from `tabStock Ledger Entry` sle
        where sle.warehouse = %(wh)s and sle.is_cancelled = 0
          and sle.posting_date between %(f)s and %(t)s and sle.actual_qty < 0
        group by sle.item_code
    """, {"wh": store, "f": from_date, "t": to_date}, as_dict=True):
        actual[r.item_code] = float(r.qty or 0)

    out = []
    for code in sorted(set(theory) | set(actual)):
        th, ac = round(theory.get(code, 0), 3), round(actual.get(code, 0), 3)
        out.append({
            "item_code": code,
            "item_name": frappe.db.get_value("Item", code, "item_name") or code,
            "uom": frappe.db.get_value("Item", code, "stock_uom"),
            "theoretical": th, "actual": ac,
            "difference": round(ac - th, 3),
            "pct": round(((ac - th) / th * 100), 1) if th else None,
        })
    out.sort(key=lambda r: abs(r["difference"]), reverse=True)
    return out
