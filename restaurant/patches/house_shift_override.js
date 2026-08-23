
// One house shift: erpnext bills against the newest open POS Opening Entry per
// profile, so the stock per-user lookup stranded every other waiter.
(() => {
  const Controller = window.erpnext && erpnext.PointOfSale && erpnext.PointOfSale.RestaurantController;
  if (!Controller || Controller.prototype.__house_shift) return;
  Controller.prototype.__house_shift = true;

  Controller.prototype.check_opening_entry = function (pos_profile) {
    const profile = pos_profile || (window.RM && RM.pos_profile && RM.pos_profile.name);
    return new Promise(resolve => {
      frappe.call("restaurant_management.house.house_shift", { pos_profile: profile }).then(({ message }) => {
        if (!message) return this.create_opening_voucher();

        if (message.stale) {
          frappe.msgprint({
            title: __("Yesterday's shift is still open"),
            indicator: "orange",
            message: __("Shift {0} started {1}. Close it and open today's shift, or billing will be refused.", [
              message.name, frappe.datetime.str_to_user(message.period_start_date),
            ]),
          });
        } else if (message.conflicts) {
          frappe.msgprint({
            title: __("More than one shift is open"),
            indicator: "orange",
            message: __("This POS Profile has {0} extra open shift(s). Close them or billing will be refused.", [
              message.conflicts,
            ]),
          });
        }

        this.prepare_app_defaults(message);
        resolve(message);
      });
    });
  };
})();
