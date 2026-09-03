# Deliveries, end to end. Upstream keyed the fee on an Address's
# `posa_delivery_charges` and a "Delivery Charges" doctype that do not exist
# here, so a paid delivery lost its fee (or 500'd). The fee is the check's own
# charge_amount, booked to the admin's RM Delivery Charges account; the address
# is free text on the check; and both ticket payloads carry them to the kitchen.
# Every section guards itself: a rebake must re-apply whatever is still missing.
ORDER = "apps/restaurant_management/restaurant_management/restaurant_management/doctype/table_order/table_order.py"
OBJ = "apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_object/restaurant_object.py"
JS = "apps/restaurant_management/restaurant_management/public/restaurant/js/table-order-class.js"


def replace_once(src, old, new, what):
    if old not in src:
        raise SystemExit("delivery: %s anchor not found" % what)
    return src.replace(old, new, 1)


# ---- server: the fee on the bill, the typed address, the dispatched ticket ----
# The helper lives at the TOP of the module: the build strips and re-appends the
# blocks at the end of this file every bake, and anything appended after them
# is cut too — a helper appended at the end vanished on the first rebake.
src = open(ORDER).read()
if "def _rm_delivery_fee" not in src:
    src = replace_once(src, 'status_attending = "Attending"\n', '''status_attending = "Attending"


def _rm_delivery_fee(company=None):
    """The admin's fee record for this company; zeros when none is set up."""
    filters = {"disabled": 0}
    if company:
        filters["company"] = company
    row = frappe.db.get_value("RM Delivery Charges", filters,
                              ["name", "default_rate", "shipping_account", "cost_center"], as_dict=True)
    return row or frappe._dict(name=None, default_rate=0, shipping_account=None, cost_center=None)
''', "module head")
    open(ORDER, "w").write(src)
    print("delivery: fee helper at the module head")

if "rm_delivery_fee:" in src:
    print("delivery: server side already applied")
else:
    src = replace_once(src, '''        if self.is_delivery == 1 and self.delivery_branch != 1 and self.address:
            address = frappe.db.get_value(
                "Address", self.address, "posa_delivery_charges")
            shipping_data = frappe.db.get_value("Delivery Charges", address, [
                                                "default_rate", "shipping_account", "cost_center"], as_dict=True)

            if not isinstance(shipping_data, type(None)):
                invoice.append('taxes', {
                    "charge_type": "Actual",
                    "account_head": shipping_data.shipping_account,
                    "rate": 0,
                    "tax_amount": shipping_data.default_rate or 0,
                    "description": shipping_data.shipping_account,
                    "cost_center": shipping_data.cost_center,
                    "included_in_print_rate": 0
                })
''', '''        # rm_delivery_fee: the check's own charge, booked to the admin's account
        if self.is_delivery == 1 and self.delivery_branch != 1 and frappe.utils.flt(self.charge_amount):
            fee = _rm_delivery_fee(self.company)
            if fee.shipping_account:
                invoice.append('taxes', {
                    "charge_type": "Actual",
                    "account_head": fee.shipping_account,
                    "rate": 0,
                    "tax_amount": frappe.utils.flt(self.charge_amount),
                    "description": _("Delivery"),
                    "cost_center": fee.cost_center,
                    "included_in_print_rate": 0
                })
''', "make_invoice fee block")

    src = replace_once(src, '''    def get_delivery_address(self, address=None):
        if not address:
            return {
                "address": "",
                "charges": 0
            }

        _address = frappe.get_doc("Address", address)

        charges = 0 if self.delivery_branch == 1 else frappe.db.get_value(
            "Delivery Charges", _address.posa_delivery_charges, "default_rate"
        )

        return dict(
            address=_address.get_display(),
            charges=charges
        )
''', '''    def get_delivery_address(self, address=None):
        # No Address record for a walk-in delivery: the text typed at seating is
        # the address, and the fee is the check's own (or the admin's default).
        charges = 0 if self.delivery_branch == 1 else (
            frappe.utils.flt(self.charge_amount) or _rm_delivery_fee(self.company).default_rate or 0)
        if not address:
            return {"address": self.get("delivery_notes") or "", "charges": charges}
        _address = frappe.get_doc("Address", address)
        return dict(address=_address.get_display(), charges=charges)
''', "get_delivery_address")

    # the dispatched ticket must say where it goes, like the board's own fetch does
    src = replace_once(src, '''                row["room_description"] = ""
                row["waiter"] = self.get("waiter")''', '''                row["room_description"] = ""
                row["waiter"] = self.get("waiter")
                row["is_delivery"] = self.is_delivery
                row["customer"] = self.customer
                row["delivery_address"] = self.get_delivery_address(self.address)["address"]''', "dispatch row")

    open(ORDER, "w").write(src)
    print("delivery: fee on the bill, address on the dispatched ticket")

# ---- server: the board's own fetch carries the same three fields ----
osrc = open(OBJ).read()
if "_rm_delivery_info" in osrc:
    print("delivery: board payload already carries it")
else:
    osrc = replace_once(osrc, '''            waiter=frappe.db.get_value("Table Order", entry.parent, "waiter"),
        )''', '''            waiter=frappe.db.get_value("Table Order", entry.parent, "waiter"),
            **_rm_delivery_info(entry.parent),
        )''', "get_command_data")
    osrc = osrc.rstrip() + '''


def _rm_delivery_info(order):
    """Delivery flag, guest and address for a ticket, from its check."""
    row = frappe.db.get_value("Table Order", order, ["is_delivery", "customer", "delivery_notes", "address"],
                              as_dict=True) or frappe._dict()
    where = row.get("delivery_notes") or ""
    if row.get("address"):
        try:
            where = frappe.get_doc("Address", row.address).get_display()
        except Exception:
            pass
    return {"is_delivery": row.get("is_delivery") or 0, "customer": row.get("customer"), "delivery_address": where}
'''
    open(OBJ, "w").write(osrc)
    print("delivery: board payload carries flag, guest and address")

# ---- client: the pay screen asked for the fee only when an Address record existed ----
js = open(JS).read()
if "rm_delivery_fee" in js:
    print("delivery: pad already asks the server for the fee")
else:
    js = replace_once(js, '''  get_delivery_address() {
    const address = this.data.address

    return new Promise(resolve => {
      if (address.length === 0) {
        resolve({});
      }

      frappeHelper.api.call({
        model: "Table Order",
        name: this.data.name,
        method: "get_delivery_address",
        args: { address },''', '''  get_delivery_address() {
    // rm_delivery_fee: no Address record is the normal case — the server has
    // the typed address and the check's own fee
    const address = this.data.address || "";

    return new Promise(resolve => {
      frappeHelper.api.call({
        model: "Table Order",
        name: this.data.name,
        method: "get_delivery_address",
        args: { address },''', "get_delivery_address (client)")
    open(JS, "w").write(js)
    print("delivery: the pay screen keeps the fee for a walk-in delivery")

# ---- client: the pay screen demanded an Address RECORD for a delivery ----
PAY = "apps/restaurant_management/restaurant_management/public/restaurant/js/pay-form-class.js"
pay = open(PAY).read()
if "rm_delivery_address_optional" in pay:
    print("delivery: pay screen already takes the typed address")
else:
    OLD_REQD = '            this.set_field_property("address", "reqd", 1);'
    NEW_REQD = ('            this.set_field_property("address", "reqd", 0);'
                '   // rm_delivery_address_optional: the typed address is enough')
    pay = replace_once(pay, OLD_REQD, NEW_REQD, "pay form address reqd")
    open(PAY, "w").write(pay)
    print("delivery: the pay screen no longer demands an Address record")
