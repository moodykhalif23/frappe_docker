# What the recipes say was used against what actually left the shelf. The gap
# is waste, over-portioning or something walking out of the door.

import frappe

from restaurant_management.inventory import variance


def execute(filters=None):
	filters = frappe._dict(filters or {})
	rows = variance(filters.get("from_date") or frappe.utils.today(),
	                filters.get("to_date") or frappe.utils.today(),
	                filters.get("warehouse"))
	return columns(), rows


def columns():
	return [
		{"label": "Item", "fieldname": "item_name", "fieldtype": "Data", "width": 220},
		{"label": "Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": "UOM", "fieldname": "uom", "fieldtype": "Data", "width": 70},
		{"label": "Recipes Say", "fieldname": "theoretical", "fieldtype": "Float", "precision": 3, "width": 120},
		{"label": "Actually Left", "fieldname": "actual", "fieldtype": "Float", "precision": 3, "width": 120},
		{"label": "Gap", "fieldname": "difference", "fieldtype": "Float", "precision": 3, "width": 100},
		{"label": "Gap %", "fieldname": "pct", "fieldtype": "Percent", "width": 90},
	]
