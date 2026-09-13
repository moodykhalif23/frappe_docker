# ERPNext-side export for the Etham public QR menu (etham.cli.ke).
#
# One whitelisted endpoint that reassembles the live Restaurant Menu ("menu 1")
# into the section/item/price shape the Hostinger menu app expects, so its
# /sync needs a single authenticated HTTP call.
#
# Identity, so the Hostinger side can keep its presentation (hero photos,
# kickers, badges) across edits and renames:
#   * item id      = the Restaurant Menu Item child-row `name` (a stable Frappe
#                    hash). It does NOT change when the item or its group is
#                    renamed, which is what makes item matching — and section
#                    re-matching by item vote — reliable.
#   * section id   = the item_group. Explicit, so the importer matches a section
#                    by id first and only falls back to title/among-items.
#
# Reads through frappe.db so any authenticated API user (token) can call it.
import frappe
from frappe.utils import flt, strip_html_tags

DEFAULT_MENU = "menu 1"

# Item groups that live on the operational menu but are not customer-facing.
# Edit this set to hide a group from the public QR menu without touching ERPNext.
EXCLUDE_GROUPS = {"Services"}


def _selling_price_list():
    return frappe.db.get_single_value("Selling Settings", "selling_price_list") or "Standard Selling"


def _price_minor(item_code, price_list):
    rate = frappe.db.get_value(
        "Item Price",
        {"item_code": item_code, "price_list": price_list, "selling": 1},
        "price_list_rate",
    )
    if rate is None:
        rate = frappe.db.get_value("Item Price", {"item_code": item_code, "selling": 1}, "price_list_rate")
    if rate is None:
        rate = frappe.db.get_value("Item", item_code, "standard_rate") or 0
    return int(round(flt(rate) * 100))


def _clean(text):
    return strip_html_tags(text or "").strip()


@frappe.whitelist()
def menu_export(menu=DEFAULT_MENU):
    if not frappe.db.exists("Restaurant Menu", menu):
        # tolerate a stale caller (e.g. the old "Etham Eatery") — use the sole menu
        names = frappe.get_all("Restaurant Menu", pluck="name", limit=1)
        if not names:
            frappe.throw("No Restaurant Menu found")
        menu = names[0]

    price_list = _selling_price_list()
    rows = frappe.db.sql(
        """
        select rmi.name as row_name, rmi.item as item_code,
               rmi.item_group as item_group, rmi.status as status, rmi.idx as idx
        from `tabRestaurant Menu Item` rmi
        where rmi.parent=%s and rmi.parenttype='Restaurant Menu'
        order by rmi.idx
        """,
        (menu,),
        as_dict=True,
    )

    sections = {}
    order = []
    for r in rows:
        code = r["item_code"]
        it = frappe.db.get_value(
            "Item", code, ["item_name", "description", "item_group", "disabled"], as_dict=True
        ) or {}
        grp = r["item_group"] or it.get("item_group") or "Menu"
        if grp in EXCLUDE_GROUPS:
            continue
        if grp not in sections:
            sections[grp] = {"id": grp, "title": grp, "items": []}
            order.append(grp)
        name = it.get("item_name") or code
        desc = _clean(it.get("description"))
        if desc == name:
            desc = ""
        sections[grp]["items"].append(
            {
                "id": r["row_name"],
                "name": name,
                "group": grp,
                "description": desc,
                "available": int(r["status"] or 0) == 1 and not int(it.get("disabled") or 0),
                "prices": [{"label": "", "minor": _price_minor(code, price_list)}],
            }
        )

    out_sections = [sections[g] for g in order]
    n_items = sum(len(s["items"]) for s in out_sections)
    return {
        "menu": menu,
        "sections": out_sections,
        "counts": {"sections": len(out_sections), "items": n_items, "source_rows": len(rows)},
    }
