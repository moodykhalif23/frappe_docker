
// One house shift: erpnext bills against the newest open POS Opening Entry per
// profile, so the stock per-user lookup stranded every other waiter.
window.RM_house_shift = function (pos, pos_profile) {
  const profile = pos_profile || (window.RM && RM.pos_profile && RM.pos_profile.name);
  return new Promise(resolve => {
    frappe.call("restaurant_management.house.house_shift", { pos_profile: profile }).then(({ message }) => {
      if (!message) {
        // Opening the drawer is a manager's act with a counted float, so the
        // first waiter to ring a dish is told, not handed the opening dialog.
        frappe.msgprint({
          title: __("The counter is closed"),
          indicator: "red",
          message: __("A manager opens the day from the floor, with the float counted into the drawer. Nothing can be billed until then."),
        });
        return resolve(null);
      }

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

      pos.prepare_app_defaults(message);
      resolve(message);
    });
  });
};
