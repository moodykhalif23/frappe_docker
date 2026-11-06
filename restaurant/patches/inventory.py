# What the kitchen actually burns: a sale, its recipe, and the stock that leaves.

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


def _uses(item_code):
    """What ONE of a dish takes from kitchen stock, as (stock item, unit, how many).

    rm_kitchen_stock: the dish's own "Kitchen stock used" table first (set on the
    till's Kitchen setup or the Item form); else its recipe, the active BOM.
    Components are issued as listed: a prepped sub-item that is stocked was
    produced by its own entry, so exploding it would double-count."""
    if frappe.db.table_exists("Dish Stock Use"):
        rows = frappe.get_all("Dish Stock Use", filters={"parent": item_code, "parenttype": "Item"},
                              fields=["stock_item", "portions"], order_by="idx")
        if rows:
            return [(r.stock_item, frappe.db.get_value("Item", r.stock_item, "stock_uom"),
                     frappe.utils.flt(r.portions)) for r in rows]
    bom = _recipe(item_code)
    if not bom:
        return None
    batch = bom.quantity or 1
    return [(c.item_code, c.uom, (c.qty or 0) / batch)
            for c in frappe.get_all("BOM Item", filters={"parent": bom.name}, fields=["item_code", "qty", "uom"])]


def _needs(invoices):
    """Stock owed by these invoices, and the dishes that use none."""
    need, uncosted, uses_of = {}, {}, {}
    for inv in invoices:
        for it in frappe.get_all("POS Invoice Item", filters={"parent": inv},
                                 fields=["item_code", "qty"]):
            if it.item_code not in uses_of:
                uses_of[it.item_code] = _uses(it.item_code)
            uses = uses_of[it.item_code]
            if not uses:
                uncosted[it.item_code] = uncosted.get(it.item_code, 0) + (it.qty or 0)
                continue
            for code, uom, per_dish in uses:
                if not frappe.db.get_value("Item", code, "is_stock_item"):
                    continue
                key = (code, uom)
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


# ---- the kitchen's daily sheet (rm_kitchen_stock) ---------------------------
# The kitchen counts in portions and pieces on a paper sheet: Opening, Add, Sold,
# Staff, Discard, Closing. The system keeps the same sheet:
#   Add      purchases recorded at the till, bought in kilos, chickens, packets
#            or crates and turned into portions by each item's yield;
#   Sold     every paid bill (or the day's bills at the close, if so set);
#   Staff,
#   Discard  recorded at the till, with what happened;
#   Closing  the kitchen's count, against what should be left.
# Nothing here is fixed in code. The yields are each stock item's units (one Kg =
# 6 Portion), what a dish uses is its "Kitchen stock used" table, and the rest is
# Restaurant Settings › Kitchen stock. All of it is edited on the till's Kitchen
# setup or in the ordinary forms. Nothing is issued before "Kitchen stock from".

STOCK_FROM = "rm_stock_from"
LINK_FIELD = "rm_stock_entry"
KIND_FIELD = "rm_kitchen_kind"
TILL_PURCHASE = "rm_till_purchase"
SPENT_FIELD = "rm_spent"
USES_FIELD = "rm_stock_uses"
KINDS = ("Sold", "Staff", "Discard")
EACH_BILL, AT_CLOSE = "Each paid bill", "At the day's close"
DEFAULTS = {"rm_ks_issue": EACH_BILL, "rm_ks_stock_group": "Ingredients",
            "rm_ks_expense_group": "Kitchen Expenses", "rm_ks_supplier": "Market"}
ACCOUNT_SETTING = {"Sold": "rm_ks_sold_account", "Staff": "rm_ks_staff_account",
                   "Discard": "rm_ks_discard_account"}
ACCOUNT_NAME = {"Sold": "Cost of Goods Sold", "Staff": "Staff Meals", "Discard": "Kitchen Waste"}
MANAGERS = ("Restaurant Manager", "System Manager", "Accounts Manager")


def _setting(field):
    """A Kitchen stock setting, or its default while it is blank."""
    if frappe.get_meta("Restaurant Settings").has_field(field):
        value = frappe.db.get_single_value("Restaurant Settings", field)
        if value:
            return value
    return DEFAULTS.get(field)


def _stock_from():
    """The day kitchen stock starts, or None while it is off. A blank Date setting
    reads back as 0001-01-01, so a date that early counts as blank."""
    start = _setting(STOCK_FROM)
    if start and frappe.utils.getdate(start).year > 1900:
        return frappe.utils.getdate(start)
    return None


def _abbr():
    return frappe.get_cached_value("Company", _company(), "abbr")


def _account(kind):
    """Where each way out of the kitchen lands in the books."""
    acct = _setting(ACCOUNT_SETTING[kind]) or "%s - %s" % (ACCOUNT_NAME[kind], _abbr())
    return acct if frappe.db.exists("Account", acct) else frappe.get_cached_value(
        "Company", _company(), "stock_adjustment_account")


def _till_staff():
    """Recording kitchen stock is the cashier's or manager's job, as closing the day is."""
    if not frappe.has_permission("POS Closing Entry", ptype="create"):
        frappe.throw(frappe._("Recording kitchen stock is the cashier's or manager's job."),
                     frappe.PermissionError)


def _manager():
    if not set(MANAGERS) & set(frappe.get_roles()):
        frappe.throw(frappe._("Kitchen setup is a manager's job."), frappe.PermissionError)


def _issue(need, kind, remarks, store):
    """One Material Issue for stock that left the kitchen, tagged with how it left."""
    entry = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Issue",
        "company": _company(),
        KIND_FIELD: kind,
        "remarks": remarks,
        "items": [{"item_code": code, "qty": round(qty, 4), "uom": uom, "s_warehouse": store,
                   "expense_account": _account(kind), "allow_zero_valuation_rate": 1}
                  for (code, uom), qty in sorted(need.items()) if qty > 0],
    })
    entry.insert(ignore_permissions=True)
    entry.submit()
    return entry


def consume_invoice(invoice):
    """Issue one paid bill's stock. Safe to run twice: the bill row is locked and
    marked in the same transaction as its entry."""
    start = _stock_from()
    if not start or not frappe.db.has_column("POS Invoice", BACKFLUSH_FIELD):
        return None
    bill = frappe.db.get_value("POS Invoice", invoice,
                               ["docstatus", "is_return", "posting_date", "pos_profile", BACKFLUSH_FIELD],
                               as_dict=True, for_update=True)
    if (not bill or bill.docstatus != 1 or bill.is_return or bill.get(BACKFLUSH_FIELD)
            or frappe.utils.getdate(bill.posting_date) < frappe.utils.getdate(start)):
        return None
    need, _ = _needs([invoice])
    entry = None
    if any(qty > 0 for qty in need.values()):
        entry = _issue(need, "Sold", "Sold: {0}".format(invoice), _store(bill.pos_profile)).name
    frappe.db.set_value("POS Invoice", invoice, {BACKFLUSH_FIELD: 1, LINK_FIELD: entry},
                        update_modified=False)
    frappe.db.commit()
    return entry


def queue_consumption(doc, method=None):
    """POS Invoice on_submit: the bill's stock comes off just after the sale commits,
    in the background, so stock can never slow down or fail a payment."""
    if doc.get("is_return") or not _stock_from() or _setting("rm_ks_issue") != EACH_BILL:
        return
    frappe.enqueue("restaurant_management.inventory.consume_invoice", queue="short",
                   invoice=doc.name, enqueue_after_commit=True,
                   job_id="rm_consume::" + doc.name, deduplicate=True)


def reverse_invoice(doc, method=None):
    """POS Invoice on_cancel: a voided bill puts its stock back."""
    name = frappe.db.get_value("POS Invoice", doc.name, LINK_FIELD) if frappe.db.has_column(
        "POS Invoice", LINK_FIELD) else None
    if name and frappe.db.get_value("Stock Entry", name, "docstatus") == 1:
        frappe.get_doc("Stock Entry", name).cancel()


def sweep(force=False):
    """Every 10 minutes (and at the close): issue any paid bill not yet issued."""
    start = _stock_from()
    if not start or not frappe.db.has_column("POS Invoice", BACKFLUSH_FIELD):
        return 0
    if not force and _setting("rm_ks_issue") != EACH_BILL:
        return 0
    filters = {"docstatus": 1, "is_return": 0, BACKFLUSH_FIELD: 0, "posting_date": [">=", start]}
    if not force:
        # leave the last two minutes to the background job each bill queues
        filters["creation"] = ["<", frappe.utils.add_to_date(frappe.utils.now_datetime(), minutes=-2)]
    done = 0
    for name in frappe.get_all("POS Invoice", filters=filters, pluck="name", order_by="creation", limit=500):
        try:
            if consume_invoice(name):
                done += 1
        except Exception:
            frappe.db.rollback()
            frappe.log_error(title="kitchen stock: could not issue " + name)
    return done


def issue_at_close():
    """close_day, after the closing commits: every bill of the day has its stock issued."""
    return sweep(force=True)


def _units(item_code, stock_uom):
    """The units an item is bought in, each with how many stock units it holds."""
    rows = frappe.get_all("UOM Conversion Detail", filters={"parent": item_code, "parenttype": "Item"},
                          fields=["uom", "conversion_factor"], order_by="idx")
    units = [{"uom": r.uom, "factor": frappe.utils.flt(r.conversion_factor)} for r in rows if r.uom != stock_uom]
    return units + [{"uom": stock_uom, "factor": 1}]


@frappe.whitelist()
def buyable():
    """What the till buys: kitchen stock, with the units it comes in, and kitchen expenses."""
    _till_staff()
    rows = frappe.get_all("Item", filters={"disabled": 0, "is_purchase_item": 1, "item_group": [
        "in", [_setting("rm_ks_stock_group"), _setting("rm_ks_expense_group")]]},
        fields=["name", "item_name", "stock_uom", "is_stock_item"], order_by="item_name")
    for r in rows:
        r.units = _units(r.name, r.stock_uom) if r.is_stock_item else [{"uom": r.stock_uom, "factor": 1}]
    return rows


def _mode_account(mode):
    acct = frappe.db.get_value("Mode of Payment Account", {"parent": mode, "company": _company()},
                               "default_account")
    if not acct:
        frappe.throw(frappe._("{0} has no account for {1}.").format(mode, _company()))
    return acct


@frappe.whitelist()
def record_purchase(lines, paid_from="Cash", note=None):
    """A buy paid from the till: stock comes in as portions, the money comes off the drawer."""
    _till_staff()
    lines = frappe.parse_json(lines) if isinstance(lines, str) else (lines or [])
    store = _store()
    items, total, stocked = [], 0.0, False
    for line in lines:
        line = frappe._dict(line)
        qty, amount = frappe.utils.flt(line.qty), frappe.utils.flt(line.amount)
        if not line.item_code or qty <= 0:
            frappe.throw(frappe._("Each line needs an item and a quantity."))
        if amount < 0:
            frappe.throw(frappe._("An amount paid cannot be negative."))
        item = frappe.db.get_value("Item", line.item_code, ["stock_uom", "is_stock_item"], as_dict=True)
        if not item:
            frappe.throw(frappe._("Unknown item {0}.").format(line.item_code))
        uom = line.uom or item.stock_uom
        factor = 1 if uom == item.stock_uom else frappe.db.get_value(
            "UOM Conversion Detail", {"parent": line.item_code, "parenttype": "Item", "uom": uom},
            "conversion_factor")
        if not factor:
            frappe.throw(frappe._("{0} is not bought in {1}.").format(line.item_code, uom))
        row = {"item_code": line.item_code, "qty": qty, "uom": uom, "conversion_factor": factor,
               "rate": amount / qty}
        if item.is_stock_item:
            row["warehouse"] = store
            stocked = True
        items.append(row)
        total += amount
    if not items:
        frappe.throw(frappe._("Add at least one item."))

    pi = frappe.get_doc({
        "doctype": "Purchase Invoice",
        "supplier": _setting("rm_ks_supplier"),
        "company": _company(),
        "update_stock": 1 if stocked else 0,
        "set_warehouse": store if stocked else None,
        "is_paid": 1,
        "mode_of_payment": paid_from,
        "cash_bank_account": _mode_account(paid_from),
        "paid_amount": total,
        "disable_rounded_total": 1,
        TILL_PURCHASE: 1,
        "remarks": (note or "").strip() or "Bought for the kitchen, paid from the till",
        "items": items,
    })
    pi.insert(ignore_permissions=True)
    pi.submit()
    frappe.db.commit()
    return {"name": pi.name, "total": pi.grand_total, "lines": len(items), "paid_from": paid_from}


@frappe.whitelist()
def kitchen_items():
    """The rows of the kitchen's sheet: active stock items, counted in their own unit."""
    _till_staff()
    return frappe.get_all("Item", filters={"disabled": 0, "is_stock_item": 1,
                                           "item_group": _setting("rm_ks_stock_group")},
                          fields=["name", "item_name", "stock_uom"], order_by="item_name")


@frappe.whitelist()
def record_kitchen_use(lines, kind, reason=None):
    """Stock that left the kitchen without a bill: staff meals and discards."""
    _till_staff()
    if kind not in ("Staff", "Discard"):
        frappe.throw(frappe._("Staff or Discard?"))
    reason = (reason or "").strip()
    if kind == "Discard" and not reason:
        frappe.throw(frappe._("Say why it was thrown away: an unexplained loss is a guess."))
    lines = frappe.parse_json(lines) if isinstance(lines, str) else (lines or [])
    need = {}
    for line in lines:
        line = frappe._dict(line)
        qty = frappe.utils.flt(line.qty)
        if not line.item_code or qty <= 0:
            frappe.throw(frappe._("Each line needs an item and how many."))
        key = (line.item_code, frappe.db.get_value("Item", line.item_code, "stock_uom"))
        need[key] = need.get(key, 0) + qty
    if not need:
        frappe.throw(frappe._("Add at least one item."))
    entry = _issue(need, kind, "{0}: {1}".format(kind, reason or "staff meals"), _store())
    frappe.db.commit()
    return {"entry": entry.name, "kind": kind, "lines": len(need)}


@frappe.whitelist()
def stock_sheet(day=None):
    """The kitchen's sheet for one day, read off the stock ledger."""
    _till_staff()
    day = frappe.utils.getdate(day or frappe.utils.today())
    store = _store()
    items = frappe.get_all("Item", filters={"disabled": 0, "is_stock_item": 1,
                                            "item_group": _setting("rm_ks_stock_group")},
                           fields=["name", "item_name", "stock_uom"], order_by="item_name")
    if not items:
        return {"day": str(day), "rows": [], "from": str(_stock_from() or "")}
    args = {"wh": store, "day": day, "codes": [i.name for i in items]}
    # The opening is the BALANCE the day starts with, never a sum of movements: ERPNext writes a count as a 0 movement
    # and the new balance (seen on the till copy, 31 Oct), so after the first count a sum is wrong every day.
    opening = {i.name: frappe.utils.flt(frappe.db.get_value(
        "Stock Ledger Entry", {"item_code": i.name, "warehouse": store, "is_cancelled": 0, "posting_date": ["<", day]},
        "qty_after_transaction", order_by="posting_date desc, posting_time desc, creation desc")) for i in items}
    # the opening count itself, on its own day, is that day's opening - not its closing count
    for code, qty in frappe.db.sql("""
        select sri.item_code, sri.qty from `tabStock Reconciliation Item` sri
        join `tabStock Reconciliation` sr on sr.name = sri.parent
        where sr.docstatus = 1 and sr.purpose = 'Opening Stock' and sr.posting_date = %(day)s
          and sri.warehouse = %(wh)s and sri.item_code in %(codes)s
        order by sr.posting_time, sr.creation""", args):
        opening[code] = frappe.utils.flt(qty)
    blank = {"add": 0.0, "sold": 0.0, "staff": 0.0, "discard": 0.0, "other": 0.0}
    moved = {}
    for code, vtype, kind, qty in frappe.db.sql("""
        select sle.item_code, sle.voucher_type, se.{kind}, sum(sle.actual_qty)
        from `tabStock Ledger Entry` sle
        left join `tabStock Entry` se on sle.voucher_type = 'Stock Entry' and se.name = sle.voucher_no
        where sle.warehouse = %(wh)s and sle.is_cancelled = 0 and sle.posting_date = %(day)s
          and sle.item_code in %(codes)s
        group by sle.item_code, sle.voucher_type, se.{kind}""".format(kind=KIND_FIELD), args):
        m = moved.setdefault(code, dict(blank))
        qty = frappe.utils.flt(qty)
        if kind in KINDS:
            m[kind.lower()] -= qty
        elif vtype == "Stock Reconciliation":
            continue  # the count itself: shown as Counted, not as a movement
        elif qty > 0 and vtype in ("Purchase Invoice", "Purchase Receipt", "Stock Entry"):
            m["add"] += qty
        else:
            m["other"] += qty
    counted = {}
    for code, qty in frappe.db.sql("""
        select sri.item_code, sri.qty from `tabStock Reconciliation Item` sri
        join `tabStock Reconciliation` sr on sr.name = sri.parent
        where sr.docstatus = 1 and sr.purpose != 'Opening Stock' and sr.posting_date = %(day)s
          and sri.warehouse = %(wh)s and sri.item_code in %(codes)s
        order by sr.posting_date, sr.posting_time, sr.creation""", args):
        counted[code] = frappe.utils.flt(qty)
    rows = []
    for it in items:
        m = moved.get(it.name, blank)
        op = opening.get(it.name, 0.0)
        expected = op + m["add"] - m["sold"] - m["staff"] - m["discard"] + m["other"]
        c = counted.get(it.name)
        rows.append({"item_code": it.name, "item_name": it.item_name, "uom": it.stock_uom,
                     "opening": round(op, 2), "add": round(m["add"], 2), "sold": round(m["sold"], 2),
                     "staff": round(m["staff"], 2), "discard": round(m["discard"], 2),
                     "other": round(m["other"], 2), "expected": round(expected, 2),
                     "counted": c, "difference": None if c is None else round(c - expected, 2)})
    return {"day": str(day), "rows": rows, "from": str(_stock_from() or "")}


@frappe.whitelist()
def record_count(counts, opening=0):
    """The kitchen's count of what is really left. The gap to the ledger is written
    off (or found) in one Stock Reconciliation; the first count opens the books."""
    _till_staff()
    counts = frappe.parse_json(counts) if isinstance(counts, str) else (counts or {})
    store = _store()
    rows = []
    for code, qty in counts.items():
        if qty in (None, ""):
            continue
        qty = frappe.utils.flt(qty)
        if qty < 0:
            frappe.throw(frappe._("A count cannot be negative ({0}).").format(code))
        have = frappe.utils.flt(frappe.db.get_value("Bin", {"item_code": code, "warehouse": store}, "actual_qty"))
        if round(have, 4) == round(qty, 4):
            continue
        rate = frappe.utils.flt(frappe.db.get_value("Bin", {"item_code": code, "warehouse": store}, "valuation_rate")) \
            or frappe.utils.flt(frappe.db.get_value("Item", code, "valuation_rate"))
        rows.append({"item_code": code, "warehouse": store, "qty": qty, "valuation_rate": rate,
                     "allow_zero_valuation_rate": 0 if rate else 1})
    if not rows:
        return {"entry": None, "changed": 0}
    # ERPNext's own rule: with no stock ledger entry at all, any count is the opening (an expense account is refused)
    first = frappe.utils.cint(opening) or not frappe.db.sql("select name from `tabStock Ledger Entry` limit 1")
    sr = frappe.get_doc({
        "doctype": "Stock Reconciliation",
        "company": _company(),
        "purpose": "Opening Stock" if first else "Stock Reconciliation",
        "expense_account": ("Temporary Opening - %s" % _abbr()) if first else _account("Discard"),
        "items": rows,
    })
    sr.insert(ignore_permissions=True)
    sr.submit()
    frappe.db.commit()
    return {"entry": sr.name, "changed": len(rows)}


# ---- Kitchen setup: everything above that is a number or a choice ------------

def _menu_dishes():
    return sorted({r.item for r in frappe.get_all("Restaurant Menu Item", fields=["item"]) if r.item})


@frappe.whitelist()
def kitchen_setup():
    """Everything the kitchen sheet runs on, for the till's Kitchen setup."""
    _manager()
    items = frappe.get_all("Item", filters={"is_stock_item": 1, "item_group": _setting("rm_ks_stock_group")},
                           fields=["name", "item_name", "stock_uom", "disabled", "valuation_rate"],
                           order_by="item_name")
    for it in items:
        bought = [u for u in _units(it.name, it.stock_uom) if u["uom"] != it.stock_uom]
        it.bought_in = bought[0]["uom"] if bought else ""
        it.per = bought[0]["factor"] if bought else 1
        # what the kitchen pays for one bought unit, as it thinks of it (KES per kg)
        it.cost = round(frappe.utils.flt(it.valuation_rate) * (it.per or 1), 2)
        it.active = 0 if it.disabled else 1
        it.code = it.name
    dishes = _menu_dishes()
    uses = frappe.get_all("Dish Stock Use", filters={"parenttype": "Item", "parent": ["in", dishes or ["-"]]},
                          fields=["parent", "stock_item", "portions"], order_by="parent, idx") \
        if frappe.db.table_exists("Dish Stock Use") else []
    expenses = frappe.get_all("Item", filters={"is_stock_item": 0, "item_group": _setting("rm_ks_expense_group")},
                              fields=["name", "item_name", "stock_uom", "disabled"], order_by="item_name")
    for e in expenses:
        e.code, e.active = e.name, 0 if e.disabled else 1
        e.account = frappe.db.get_value("Item Default", {"parent": e.name, "company": _company()}, "expense_account")
    return {"items": items, "expenses": expenses,
            "uses": [{"dish": u.parent, "stock_item": u.stock_item, "portions": u.portions} for u in uses],
            "dishes": dishes, "stock_group": _setting("rm_ks_stock_group"),
            "units": frappe.get_all("UOM", filters={"enabled": 1} if frappe.db.has_column("UOM", "enabled") else {},
                                    pluck="name", order_by="name")}


def _stock_group_account():
    """With the company's item-wise inventory accounts on (Etham's are), ERPNext posts no count, purchase or issue for
    an item that does not name its inventory account - on the item, its group or its brand. The kitchen stock group
    names the company's default inventory account, unless it already names one (found on the till copy, 31 Oct)."""
    company = _company()
    if not (frappe.get_meta("Company").has_field("enable_item_wise_inventory_account")
            and frappe.get_meta("Item Default").has_field("default_inventory_account")
            and frappe.get_cached_value("Company", company, "enable_item_wise_inventory_account")):
        return
    group = frappe.get_doc("Item Group", _setting("rm_ks_stock_group"))
    row = next((d for d in group.get("item_group_defaults") if d.company == company), None)
    if row and row.default_inventory_account:
        return
    account = frappe.get_cached_value("Company", company, "default_inventory_account")
    if not account:
        frappe.throw(frappe._("{0} keeps an inventory account per item: set its default inventory account first.").format(company))
    if not row:
        row = group.append("item_group_defaults", {"company": company})
    row.default_inventory_account = account
    group.flags.ignore_permissions = True
    group.save()


def _series_caught_up(doctype):
    """A series counter behind the names already used makes every new document a duplicate, and the failed save rolls
    the counter back, so it never recovers: Etham's ACC-PINV-2026- read 0 beside the six demo purchase invoices of
    21 Aug, and the first till purchase failed (found on the till copy, 31 Oct). Each of the doctype's series is moved
    up to the highest number in use - never down."""
    from frappe.model.naming import parse_naming_series
    field = frappe.get_meta(doctype).get_field("naming_series")
    for option in ((field.options or "") if field else "").split("\n"):
        option = option.strip()
        if not option:
            continue
        keys = []   # the counter's key, without taking a number
        parse_naming_series(option if "#" in option else option + ".#####",
                            number_generator=lambda key, digits: keys.append(key) or "")
        for key in keys:
            top = frappe.utils.cint(frappe.db.sql(
                "select max(cast(substring(name, %s) as unsigned)) from `tab{0}` where name like %s".format(doctype),
                (len(key) + 1, key + "%"))[0][0])
            current = frappe.db.sql("select current from `tabSeries` where name = %s", key)
            if current and frappe.utils.cint(current[0][0]) >= top:
                continue
            if current:
                frappe.db.sql("update `tabSeries` set current = %s where name = %s", (top, key))
            elif top:
                frappe.db.sql("insert into `tabSeries` (name, current) values (%s, %s)", (key, top))


@frappe.whitelist()
def save_kitchen_items(rows):
    """Add or change kitchen stock items and their yields (one bought unit = n of the counted unit)."""
    _manager()
    _stock_group_account()
    rows = frappe.parse_json(rows) if isinstance(rows, str) else (rows or [])
    group, store = _setting("rm_ks_stock_group"), _store()
    for row in rows:
        row = frappe._dict(row)
        name = (row.item_name or "").strip()
        if not name:
            continue
        counted = row.stock_uom or "Portion"
        bought, per = (row.bought_in or "").strip(), frappe.utils.flt(row.per)
        if bought and bought != counted and per <= 0:
            frappe.throw(frappe._("{0}: how many {1} does one {2} give?").format(name, counted, bought))
        if row.code and frappe.db.exists("Item", row.code):
            item = frappe.get_doc("Item", row.code)
        else:
            code = "STK-" + name
            if frappe.db.exists("Item", code):
                frappe.throw(frappe._("There is already a kitchen item called {0}.").format(name))
            item = frappe.new_doc("Item")
            item.update({"item_code": code, "item_group": group, "is_stock_item": 1, "is_purchase_item": 1,
                         "is_sales_item": 0, "include_item_in_manufacturing": 1,
                         "item_defaults": [{"company": _company(), "default_warehouse": store}]})
        item.item_name = name
        # the counted unit can change only while nothing has moved for the item
        if item.is_new() or not frappe.db.exists("Stock Ledger Entry", {"item_code": item.name}):
            item.stock_uom = counted
        units = [u for u in item.get("uoms") if u.uom not in (item.stock_uom, bought)]
        item.set("uoms", [{"uom": item.stock_uom, "conversion_factor": 1}]
                 + [{"uom": u.uom, "conversion_factor": u.conversion_factor} for u in units]
                 + ([{"uom": bought, "conversion_factor": per}] if bought and bought != item.stock_uom else []))
        if row.cost not in (None, ""):
            item.valuation_rate = frappe.utils.flt(row.cost) / (per if bought and per > 0 else 1)
        item.disabled = 0 if frappe.utils.cint(row.get("active", 1)) else 1
        item.flags.ignore_permissions = True
        item.save()
    frappe.db.commit()
    return kitchen_setup()


@frappe.whitelist()
def save_expense_items(rows):
    """Add or change what the till buys without counting it (charcoal, gas, transport),
    and the expense account each is booked to."""
    _manager()
    rows = frappe.parse_json(rows) if isinstance(rows, str) else (rows or [])
    group = _setting("rm_ks_expense_group")
    for row in rows:
        row = frappe._dict(row)
        name = (row.item_name or "").strip()
        if not name:
            continue
        if row.code and frappe.db.exists("Item", row.code):
            item = frappe.get_doc("Item", row.code)
        else:
            code = "EXP-" + name
            if frappe.db.exists("Item", code):
                frappe.throw(frappe._("There is already a kitchen expense called {0}.").format(name))
            item = frappe.new_doc("Item")
            item.update({"item_code": code, "item_group": group, "is_stock_item": 0, "is_purchase_item": 1,
                         "is_sales_item": 0, "stock_uom": row.stock_uom or "Unit"})
        item.item_name = name
        if item.is_new() and row.stock_uom:
            item.stock_uom = row.stock_uom
        account = row.account or "Miscellaneous Expenses - %s" % _abbr()
        default = next((d for d in item.get("item_defaults") if d.company == _company()), None)
        if default:
            default.expense_account = account
        else:
            item.append("item_defaults", {"company": _company(), "expense_account": account})
        item.disabled = 0 if frappe.utils.cint(row.get("active", 1)) else 1
        item.flags.ignore_permissions = True
        item.save()
    frappe.db.commit()
    return kitchen_setup()


@frappe.whitelist()
def save_dish_uses(rows, dishes=None):
    """What each dish takes from kitchen stock. Every dish named in `dishes` gets exactly
    the lines given for it (none = it stops taking stock)."""
    _manager()
    rows = frappe.parse_json(rows) if isinstance(rows, str) else (rows or [])
    dishes = frappe.parse_json(dishes) if isinstance(dishes, str) else (dishes or [])
    by_dish = {d: [] for d in dishes}
    for row in rows:
        row = frappe._dict(row)
        if not row.dish:
            continue
        if row.stock_item and frappe.utils.flt(row.portions) > 0:
            by_dish.setdefault(row.dish, []).append(row)
        else:
            by_dish.setdefault(row.dish, [])
    for dish, lines in by_dish.items():
        if not frappe.db.exists("Item", dish):
            continue
        doc = frappe.get_doc("Item", dish)
        doc.set(USES_FIELD, [{"stock_item": l.stock_item, "portions": frappe.utils.flt(l.portions)} for l in lines])
        doc.flags.ignore_permissions = True
        doc.save()
    frappe.db.commit()
    return kitchen_setup()


def ensure_kitchen_stock():
    """Idempotent: what the kitchen sheet needs. Fills only what is missing or blank."""
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    create_custom_fields({
        "POS Invoice": [
            {"fieldname": BACKFLUSH_FIELD, "fieldtype": "Check", "label": "Stock Consumed",
             "read_only": 1, "insert_after": "status", "no_copy": 1},
            {"fieldname": LINK_FIELD, "fieldtype": "Link", "options": "Stock Entry", "label": "Stock Issue",
             "read_only": 1, "no_copy": 1, "insert_after": BACKFLUSH_FIELD},
        ],
        "Stock Entry": [{"fieldname": KIND_FIELD, "fieldtype": "Select", "label": "Kitchen",
                         "options": "\nSold\nStaff\nDiscard", "read_only": 1, "no_copy": 1,
                         "in_standard_filter": 1, "insert_after": "stock_entry_type"}],
        "Purchase Invoice": [{"fieldname": TILL_PURCHASE, "fieldtype": "Check", "label": "Paid from the till",
                              "read_only": 1, "no_copy": 1, "insert_after": "is_paid"}],
        "POS Closing Entry Detail": [{"fieldname": SPENT_FIELD, "fieldtype": "Currency", "label": "Purchases",
                                      "read_only": 1, "insert_after": "rm_withdrawn",
                                      "description": "Purchases paid from this till in the shift, already taken off Expected Amount."}],
        "Item": [
            {"fieldname": "rm_ks_section", "fieldtype": "Section Break", "label": "Kitchen stock",
             "collapsible": 1, "insert_after": "description", "depends_on": "eval:!doc.is_stock_item"},
            {"fieldname": USES_FIELD, "fieldtype": "Table", "options": "Dish Stock Use",
             "label": "Kitchen stock used (for one of this dish)", "insert_after": "rm_ks_section"},
        ],
        "Restaurant Settings": [
            {"fieldname": "rm_ks_section", "fieldtype": "Section Break", "label": "Kitchen stock",
             "insert_after": "rm_tw_charges_account"},
            {"fieldname": STOCK_FROM, "fieldtype": "Date", "label": "Kitchen stock from",
             "insert_after": "rm_ks_section",
             "description": "Paid bills take their stock out from this date. Blank: stock is not touched."},
            {"fieldname": "rm_ks_issue", "fieldtype": "Select", "label": "Take stock off",
             "options": "\n%s\n%s" % (EACH_BILL, AT_CLOSE), "insert_after": STOCK_FROM},
            {"fieldname": "rm_ks_stock_group", "fieldtype": "Link", "options": "Item Group",
             "label": "Kitchen stock items are in", "insert_after": "rm_ks_issue"},
            {"fieldname": "rm_ks_expense_group", "fieldtype": "Link", "options": "Item Group",
             "label": "Kitchen expenses are in", "insert_after": "rm_ks_stock_group",
             "description": "Non-stock things bought at the till: charcoal, gas, transport."},
            {"fieldname": "rm_ks_supplier", "fieldtype": "Link", "options": "Supplier",
             "label": "Till purchases are from", "insert_after": "rm_ks_expense_group"},
            {"fieldname": "rm_ks_col", "fieldtype": "Column Break", "insert_after": "rm_ks_supplier"},
            {"fieldname": "rm_ks_sold_account", "fieldtype": "Link", "options": "Account",
             "label": "Sold stock goes to", "insert_after": "rm_ks_col"},
            {"fieldname": "rm_ks_staff_account", "fieldtype": "Link", "options": "Account",
             "label": "Staff meals go to", "insert_after": "rm_ks_sold_account"},
            {"fieldname": "rm_ks_discard_account", "fieldtype": "Link", "options": "Account",
             "label": "Discards and count differences go to", "insert_after": "rm_ks_staff_account"},
        ],
    }, ignore_validate=True)

    for uom, whole in (("Portion", 0), ("Piece", 1), ("Chicken", 0), ("Packet", 1), ("Crate", 1)):
        if not frappe.db.exists("UOM", uom):
            frappe.get_doc({"doctype": "UOM", "uom_name": uom, "must_be_whole_number": whole}).insert(
                ignore_permissions=True)
    for field in ("rm_ks_stock_group", "rm_ks_expense_group"):
        group = _setting(field)
        if not frappe.db.exists("Item Group", group):
            frappe.get_doc({"doctype": "Item Group", "item_group_name": group,
                            "parent_item_group": "All Item Groups"}).insert(ignore_permissions=True)
    _stock_group_account()
    for doctype in ("Purchase Invoice", "Stock Entry", "Stock Reconciliation"):
        _series_caught_up(doctype)
    supplier = _setting("rm_ks_supplier")
    if not frappe.db.exists("Supplier", supplier):
        group = "Local" if frappe.db.exists("Supplier Group", "Local") else frappe.db.get_value(
            "Supplier Group", {"is_group": 0}, "name")
        frappe.get_doc({"doctype": "Supplier", "supplier_name": supplier, "supplier_group": group}).insert(
            ignore_permissions=True)
    abbr = _abbr()
    for name, parent, kind in (("Staff Meals", "Indirect Expenses", "Expense Account"),
                               ("Kitchen Waste", "Stock Expenses", "Stock Adjustment")):
        if not frappe.db.exists("Account", "%s - %s" % (name, abbr)) and frappe.db.exists(
                "Account", "%s - %s" % (parent, abbr)):
            frappe.get_doc({"doctype": "Account", "account_name": name, "company": _company(),
                            "parent_account": "%s - %s" % (parent, abbr), "root_type": "Expense",
                            "account_type": kind, "is_group": 0}).insert(ignore_permissions=True)
    # the settings show what is in force: a blank is filled with its default, a choice is kept
    filled = dict(DEFAULTS)
    for kind, field in ACCOUNT_SETTING.items():
        filled[field] = _account(kind)
    for field, value in filled.items():
        if frappe.get_meta("Restaurant Settings").has_field(field) and not frappe.db.get_single_value(
                "Restaurant Settings", field):
            frappe.db.set_single_value("Restaurant Settings", field, value)
    # the owner's call (30 Oct): a count that is off never stops a sale
    if not frappe.db.get_single_value("Stock Settings", "allow_negative_stock"):
        frappe.db.set_single_value("Stock Settings", "allow_negative_stock", 1)
    default = frappe.db.get_single_value("Stock Settings", "default_warehouse")
    if not default or not frappe.db.exists("Warehouse", default):
        frappe.db.set_single_value("Stock Settings", "default_warehouse", _store())
    frappe.db.commit()
    return "ok"
