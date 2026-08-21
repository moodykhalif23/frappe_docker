

# ---- restaurant-kit extensions (appended by the patch layer) ----
# Every write below lands on standard ERPNext doctypes (Item, Item Price,
# Restaurant Menu) so frappe stays the single source of record for
# accounting, audit and reporting.

RM_STATUS_FLOW = ["Sent", "Processing", "Completed", "Delivered"]
RM_STATUS_LABELS = {
    "Pending": "Placing order", "Attending": "Placing order",
    "Sent": "Sent to kitchen", "Processing": "Being prepared",
    "Completed": "Ready to serve", "Delivered": "Served",
    "Invoiced": "Paid", "queue": "Queued",
}


@frappe.whitelist(allow_guest=True)
def order_status(order):
    """Customer-facing order tracker: item names, quantities and progress only —
    no prices, customers or internals."""
    head = frappe.db.get_value("Table Order", order, ["name", "status"], as_dict=True)
    if not head:
        return dict(found=0)
    items = frappe.get_all(
        "Order Entry Item",
        filters={"parent": order, "parenttype": "Table Order", "qty": (">", 0)},
        fields=["item_name", "qty", "status", "ordered_time"],
        order_by="ordered_time")
    for i in items:
        i["label"] = RM_STATUS_LABELS.get(i["status"], i["status"])
        i["step"] = (RM_STATUS_FLOW.index(i["status"]) + 1) if i["status"] in RM_STATUS_FLOW else 0
        i["ordered_time"] = str(i["ordered_time"] or "")
    return dict(found=1, order=head.name, short_name=head.name.split("-")[-1],
                status=head.status, flow=RM_STATUS_FLOW, steps=len(RM_STATUS_FLOW),
                items=items)


def _rm_default_menu():
    menu = frappe.db.get_value(
        "POS Profile", {"disabled": 0, "restaurant_menu": ("is", "set")}, "restaurant_menu")
    return menu or frappe.db.get_value("Restaurant Menu", {}, "name")


@frappe.whitelist()
def get_menu_item(item_code):
    frappe.has_permission("Item", "read", throw=True)
    d = frappe.db.get_value("Item", item_code,
                            ["name", "item_name", "item_group", "item_type", "image"], as_dict=True)
    if not d:
        frappe.throw("Item not found")
    pl = frappe.db.get_value("POS Profile", {"disabled": 0}, "selling_price_list") \
        or frappe.db.get_value("Price List", {"enabled": 1, "selling": 1}, "name")
    d["rate"] = frappe.db.get_value(
        "Item Price", {"item_code": item_code, "price_list": pl}, "price_list_rate")
    d["price_list"] = pl
    return d


@frappe.whitelist()
def upsert_menu_item(item_code=None, item_name=None, item_group=None, rate=None,
                     item_type=None, image=None, add_to_menu=1):
    """Create or update a menu item from the POS. Non-stock sales Item + Item
    Price rows + a Restaurant Menu entry; nothing lives outside frappe."""
    from frappe.utils import cint, flt

    if item_code:
        frappe.has_permission("Item", "write", throw=True)
        doc = frappe.get_doc("Item", item_code)
        if item_name:
            doc.item_name = item_name
        if item_group:
            doc.item_group = item_group
        if item_type:
            doc.item_type = item_type
        doc.image = image or None
        doc.save()
    else:
        frappe.has_permission("Item", "create", throw=True)
        if not (item_name and item_group):
            frappe.throw("Item name and category are required")
        doc = frappe.get_doc({
            "doctype": "Item", "item_code": item_name, "item_name": item_name,
            "item_group": item_group, "stock_uom": "Nos",
            "is_stock_item": 0, "is_sales_item": 1,
            "item_type": item_type or "Veg", "image": image or None,
        }).insert()

    if rate not in (None, ""):
        for pl in frappe.get_all("Price List", filters={"enabled": 1, "selling": 1}, pluck="name"):
            price_name = frappe.db.get_value(
                "Item Price", {"item_code": doc.name, "price_list": pl})
            if price_name:
                frappe.db.set_value("Item Price", price_name, "price_list_rate", flt(rate))
            else:
                frappe.get_doc({
                    "doctype": "Item Price", "item_code": doc.name, "price_list": pl,
                    "price_list_rate": flt(rate), "selling": 1,
                }).insert()

    if cint(add_to_menu):
        menu_name = _rm_default_menu()
        if menu_name and not frappe.db.exists(
                "Restaurant Menu Item", {"parent": menu_name, "item": doc.name}):
            menu = frappe.get_doc("Restaurant Menu", menu_name)
            field = next(f.fieldname for f in frappe.get_meta("Restaurant Menu").get_table_fields()
                         if f.options == "Restaurant Menu Item")
            menu.append(field, {"item": doc.name, "item_group": doc.item_group, "status": 1})
            menu.save(ignore_permissions=True)

    frappe.publish_realtime("update_menu", {"item_code": doc.name, "in_menu": True})
    return doc.name
