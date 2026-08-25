# What the recipes say was used, against what actually left the shelf.

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
		{"label": "Item", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 180},
		{"label": "Name", "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": "UOM", "fieldname": "uom", "fieldtype": "Data", "width": 70},
		{"label": "Recipes Say", "fieldname": "theoretical", "fieldtype": "Float", "precision": 3, "width": 120},
		{"label": "Actually Left", "fieldname": "actual", "fieldtype": "Float", "precision": 3, "width": 120},
		{"label": "Difference", "fieldname": "difference", "fieldtype": "Float", "precision": 3, "width": 110},
		{"label": "Off By %", "fieldname": "pct", "fieldtype": "Float", "precision": 1, "width": 90},
	]
