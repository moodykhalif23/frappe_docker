import frappe
from frappe.model.document import Document


class RestaurantWaiter(Document):
	def validate(self):
		pin = self.get_password("pin", raise_exception=False) if not self.is_new() else self.pin
		if pin and (not str(pin).isdigit() or not 4 <= len(str(pin)) <= 6):
			frappe.throw(frappe._("The PIN must be 4 to 6 digits"))
