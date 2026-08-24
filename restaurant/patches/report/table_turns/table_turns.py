# How hard each table worked: parties served, covers, and how long they sat.
# A turn is a booking with both a seating and a leaving stamp, so it only counts
# once the check is paid.

import frappe

from restaurant_management.house import _turn_rows


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return columns(), _turn_rows(filters.get("from_date"), filters.get("to_date"))


def columns():
	return [
		{"label": "Table", "fieldname": "table_label", "fieldtype": "Data", "width": 140},
		{"label": "Room", "fieldname": "room", "fieldtype": "Link", "options": "Restaurant Object", "width": 140},
		{"label": "Seats", "fieldname": "seats", "fieldtype": "Int", "width": 70},
		{"label": "Turns", "fieldname": "turns", "fieldtype": "Int", "width": 70},
		{"label": "Covers", "fieldname": "covers", "fieldtype": "Int", "width": 80},
		{"label": "Avg Turn (min)", "fieldname": "avg_turn", "fieldtype": "Int", "width": 130},
		{"label": "Longest (min)", "fieldname": "longest_turn", "fieldtype": "Int", "width": 120},
		{"label": "Turns / Seat", "fieldname": "turns_per_seat", "fieldtype": "Float", "precision": 2, "width": 110},
	]
