# What to buy, and how much. Reads the same numbers the floor does.

import frappe

from restaurant_management.inventory import restock_list


def execute(filters=None):
	filters = frappe._dict(filters or {})
	rows = restock_list(filters.get("warehouse"))
	if filters.get("only_short"):
		rows = [r for r in rows if r["needs_restock"]]
	return columns(), rows


def columns():
	return [
		{"label": "Item", "fieldname": "item_name", "fieldtype": "Data", "width": 220},
		{"label": "Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": "UOM", "fieldname": "uom", "fieldtype": "Data", "width": 70},
		{"label": "On Hand", "fieldname": "on_hand", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": "On Order", "fieldname": "on_order", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": "Projected", "fieldname": "projected", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": "Reorder At", "fieldname": "reorder_level", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": "Order", "fieldname": "suggested_order", "fieldtype": "Float", "precision": 2, "width": 100},
		{"label": "Restock", "fieldname": "needs_restock", "fieldtype": "Check", "width": 80},
	]
