# What the restaurant owns, counted rather than costed. erpnext's Asset refuses a
# record with no purchase amount, which is the back-and-forth this replaces.
import frappe
from frappe.model.document import Document


class RestaurantAsset(Document):
	def validate(self):
		if not self.acquired_on:
			self.acquired_on = frappe.utils.today()
		if frappe.utils.cint(self.quantity) < 1:
			self.quantity = 1
		self.asset_name = (self.asset_name or "").strip()
