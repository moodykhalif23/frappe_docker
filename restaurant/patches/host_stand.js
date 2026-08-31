
// Host stand. The stock check-in wants an existing Customer and a reservation
// window, then hides itself with no table picked — useless for a walk-in.
(() => {
  if (window.RM_host_stand) return;

  const label = (t) => {
    if (t.free === null) return `${t.description} · ${__("capacity not set")}`;
    if (!t.shared) return `${t.description} · ${__("{0} seats", [t.seats])}`;
    const who = (t.parties || []).map(p => p.guest).join(", ");
    return `${t.description} · ${__("{0} of {1} free", [t.free, t.seats])} · ${__("sharing with {0}", [who])}`;
  };

  const free_tables = (dialog) => {
    const covers = dialog.get_value("covers") || 0;
    const whole_table = dialog.get_value("whole_table") ? 1 : 0;
    return frappe.call("restaurant_management.house.free_tables", { covers, whole_table }).then(({ message }) => {
      const tables = message || [];
      const field = dialog.get_field("table");
      field.df.options = tables.map(t => ({ value: t.name, label: label(t) }));
      field.refresh();

      const seats_free = tables.reduce((n, t) => n + (t.free || 0), 0);
      dialog.fields_dict.hint.$wrapper.html(
        tables.length
          ? `<p class="text-muted small">${__("{0} seat(s) across {1} table(s) for {2}",
              [seats_free, tables.length, covers || __("any party")])}</p>`
          : `<p class="text-danger small">${__("Nowhere seats {0} — free a table, or split the party.", [covers])}</p>`
      );
      if (tables.length) dialog.set_value("table", tables[0].name);
    });
  };

  const seat = (values, dialog) => {
    const who = window.RM_waiter && RM_waiter.current;
    frappe.call({
      method: "restaurant_management.house.seat_walkin",
      args: Object.assign({}, values, { waiter: who ? who.waiter : null }),
      freeze: true,
      freeze_message: __("Seating the party..."),
    }).then(({ message }) => {
      if (!message) return;
      dialog.hide();
      window.RM_seats && RM_seats.refresh();

      const go = () => {
        // Mark the table, then select its room: rendering a room opens the marked
        // table's pad. A route with a query string is not a route in v16.
        RM.navigate_table = message.table;
        const room = window.RM && RM.object && RM.object(message.room);
        if (room && room.select) return room.select();
        RM.navigate_room = message.room;
        frappe.set_route("restaurant-manage", { restaurant_room: message.room });
      };

      const alone = message.seats && message.seats.parties.length === 1;
      if (!who || !alone) return go();
      // The section only passes to them when they have the table to themselves.
      frappe.call("restaurant_management.house.claim_table", {
        table: message.table, waiter: who.waiter, token: who.token,
      }).then(go, go);
    });
  };

  window.RM_host_stand = {
    mounted: false,

    mount(rm) {
      if (this.mounted || !rm.page || !rm.page.add_inner_button) return;
      this.mounted = true;
      rm.page.add_inner_button(__("Seat guest"), () => RM_host_stand.open(), null, "primary");
    },

    open() {
      // Seating belongs to a waiter: sign in once, then straight back here.
      if (window.RM_waiter && !RM_waiter.current) {
        frappe.show_alert({ message: __("Sign in first — the guests you seat are yours"), indicator: "blue" });
        return RM_waiter.open(() => RM_host_stand.open());
      }
      const dialog = new frappe.ui.Dialog({
        title: __("Seat a guest"),
        fields: [
          { fieldname: "guest_name", fieldtype: "Data", label: __("Guest name"), reqd: 1 },
          {
            fieldname: "covers", fieldtype: "Int", label: __("Guests"), default: 2, reqd: 1,
            change: () => free_tables(dialog),
          },
          { fieldname: "contact", fieldtype: "Data", label: __("Phone (optional)") },
          {
            fieldname: "whole_table", fieldtype: "Check", label: __("Table to themselves"),
            change: () => free_tables(dialog),
          },
          { fieldname: "table", fieldtype: "Select", label: __("Table"), reqd: 1 },
          { fieldname: "hint", fieldtype: "HTML" },
        ],
        primary_action_label: __("Seat & open order"),
        primary_action: (values) => seat(values, dialog),
      });
      dialog.show();
      free_tables(dialog);
    },
  };
})();
