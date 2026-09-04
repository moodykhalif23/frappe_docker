# The Restaurant workspace shipped shortcuts for menus and settings but none for
# the reports or the waiter list, so the only way to reach them was to know their
# names and type them into search.
import json

P = ("apps/restaurant_management/restaurant_management/restaurant_management"
     "/workspace/restaurant/restaurant.json")

WANTED = [
    {"label": "Waiters", "type": "DocType", "link_to": "Restaurant Waiter", "block": "rmWaitersBlk"},
    {"label": "Sales by Waiter", "type": "Report", "link_to": "Sales by Waiter",
     "report_ref_doctype": "POS Invoice", "doc_view": "Report", "block": "rmSalesRepBlk"},
    {"label": "M-Pesa Payments", "type": "Report", "link_to": "M-Pesa Payments",
     "report_ref_doctype": "POS Invoice", "doc_view": "Report", "block": "rmMpesaRepBlk"},
    {"label": "Table Turns", "type": "Report", "link_to": "Table Turns",
     "report_ref_doctype": "Restaurant Booking", "doc_view": "Report", "block": "rmTurnsRepBlk"},
    {"label": "Restock List", "type": "Report", "link_to": "Restock List",
     "report_ref_doctype": "Item", "doc_view": "Report", "block": "rmRestockBlk"},
    {"label": "Consumption Variance", "type": "Report", "link_to": "Consumption Variance",
     "report_ref_doctype": "Stock Ledger Entry", "doc_view": "Report", "block": "rmVarianceBlk"},
    {"label": "Recipes", "type": "DocType", "link_to": "BOM", "block": "rmBomBlk"},
    {"label": "Stock Entry", "type": "DocType", "link_to": "Stock Entry", "block": "rmStockBlk"},
]

doc = json.load(open(P))
have = {s.get("label") for s in doc.get("shortcuts", [])}
content = json.loads(doc.get("content") or "[]")
added = []

for w in WANTED:
    if w["label"] in have:
        continue
    shortcut = {
        "color": "Grey", "doc_view": w.get("doc_view", ""), "label": w["label"],
        "link_to": w["link_to"], "type": w["type"],
    }
    if w.get("report_ref_doctype"):
        shortcut["report_ref_doctype"] = w["report_ref_doctype"]
    doc.setdefault("shortcuts", []).append(shortcut)
    content.append({"id": w["block"], "type": "shortcut",
                    "data": {"shortcut_name": w["label"], "col": 3}})
    added.append(w["label"])

if added:
    doc["content"] = json.dumps(content)
# frappe re-imports a workspace only when the file is newer than the stored row:
# stamp every bake, or a shortcut added on an earlier bake never reaches a site
# that already holds the old stamp (five were missing on live for this)
import datetime
doc["modified"] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.000000")
json.dump(doc, open(P, "w"), indent=1, sort_keys=True)
open(P, "a").write("\n")
print("workspace: " + ("added " + ", ".join(added) if added else "reports already linked") + "; stamped " + doc["modified"][:19])
