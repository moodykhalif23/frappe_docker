# What to buy: on hand against the level it should not fall below.

import frappe

from restaurant_management.inventory import restock_list


def execute(filters=None):
	filters = frappe._dict(filters or {})
	rows = restock_list(filters.get("warehouse"))
	if not filters.get("show_all"):
		rows = [r for r in rows if r["needs_restock"]]
	return columns(), rows


def columns():
	return [
		{"label": "Item", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 180},
		{"label": "Name", "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": "UOM", "fieldname": "uom", "fieldtype": "Data", "width": 70},
		{"label": "On Hand", "fieldname": "on_hand", "fieldtype": "Float", "precision": 3, "width": 100},
		{"label": "On Order", "fieldname": "on_order", "fieldtype": "Float", "precision": 3, "width": 100},
		{"label": "Projected", "fieldname": "projected", "fieldtype": "Float", "precision": 3, "width": 100},
		{"label": "Reorder At", "fieldname": "reorder_level", "fieldtype": "Float", "precision": 3, "width": 100},
		{"label": "Order This", "fieldname": "suggested_order", "fieldtype": "Float", "precision": 3, "width": 110},
	]
