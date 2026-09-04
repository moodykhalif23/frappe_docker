
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
      let tables = message || [];
      // opened from a table's own pad: that table only, with its seats left
      if (dialog.__only_table) tables = tables.filter(t => t.name === dialog.__only_table);
      dialog.__rooms = Object.fromEntries(tables.map(t => [t.name, t.room]));
      const field = dialog.get_field("table");
      field.df.options = tables.map(t => ({ value: t.name, label: label(t) }));
      field.refresh();

      const seats_free = tables.reduce((n, t) => n + (t.free || 0), 0);
      dialog.fields_dict.hint.$wrapper.html(
        tables.length
          ? `<p class="text-muted small">${dialog.__only_table
              ? __("{0} seat(s) left at this table for {1}", [seats_free, covers || __("any party")])
              : __("{0} seat(s) across {1} table(s) for {2}", [seats_free, tables.length, covers || __("any party")])}</p>`
          : `<p class="text-danger small">${dialog.__only_table
              ? __("This table cannot seat {0} more — free seats first, or pick another table.", [covers])
              : __("Nowhere seats {0} — free a table, or split the party.", [covers])}</p>`
      );
      if (tables.length) dialog.set_value("table", tables[0].name);
      dialog.set_df_property("table", "read_only", dialog.__only_table ? 1 : 0);
      if (dialog.__only_table) dialog.get_primary_btn().prop("disabled", !tables.length);
      toggle_address(dialog);
    });
  };

  // A slot in the Delivery room takes an address; every other table hides it.
  let delivery = null;
  const toggle_address = (dialog) => {
    const show = () => {
      const room = (dialog.__rooms || {})[dialog.get_value("table")];
      const on = !!(delivery && delivery.room && room === delivery.room);
      dialog.set_df_property("address", "hidden", on ? 0 : 1);
      dialog.set_df_property("address", "reqd", on ? 1 : 0);
      if (on && delivery.fee) {
        dialog.set_df_property("address", "description",
          __("Delivery fee {0} is added to the bill — the till can change it.", [format_currency(delivery.fee)]));
      }
    };
    if (delivery) return show();
    frappe.call("restaurant_management.house.delivery_room").then(({ message }) => { delivery = message || {}; show(); });
  };

  // The pad is already open on this table: wait for the new check to arrive on
  // the realtime sync, select it, then do whatever the tap was for (a dish).
  const select_new_check = (om, order, then) => {
    let tries = 0;
    const tick = setInterval(() => {
      tries += 1;
      // the pad keeps its checks as children of an ObjectManage: iterate whatever shape that is
      const pool = om.orders || om.children || {};
      const list = typeof pool.values === "function" ? Array.from(pool.values()) : Object.values(pool);
      let found = list.find(o => o && o.data && o.data.name === order);
      if (!found && om.last_order && om.last_order.data && om.last_order.data.name === order) found = om.last_order;
      if (found) { clearInterval(tick); found.select(); if (then) setTimeout(then, 300); return; }
      if (tries === 5 && om.make_orders) om.make_orders();
      if (tries > 40) { clearInterval(tick); frappe.show_alert({ message: __("Seated — tap the check to open it"), indicator: "blue" }); }
    }, 250);
  };
  const seat = (values, dialog) => {
    const who = window.RM_waiter && RM_waiter.current;
    frappe.call({
      method: "restaurant_management.house.seat_walkin",
      args: Object.assign({}, values, { waiter: who ? who.waiter : null, token: who ? who.token : null }),
      freeze: true,
      freeze_message: __("Seating the party..."),
    }).then(({ message }) => {
      if (!message) return;
      dialog.hide();
      window.RM_seats && RM_seats.refresh();
      if (dialog.__om) return select_new_check(dialog.__om, message.order, dialog.__then);

      const go = () => {
        // Mark the table, then select its room: rendering a room opens the marked
        // table's pad. A route with a query string is not a route in v16.
        RM.navigate_table = message.table;
        // so the pad opens on this party's check, not on a "whose check?" prompt
        RM.navigate_order = message.order;
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

    // A dish tapped with no check selected: if the table already has a party the
    // pad simply has not loaded its checks yet — load them and let the picker
    // choose; only an empty table opens Seat guest.
    seat_or_pick(om, then) {
      const table = om.table.data.name;
      const pick = () => (window.RM_seats && RM_seats.pick_check(om, then)) || this.open_for(table, om, then);
      // the pad loads its checks as it opens: give that load a moment first
      let tries = 0;
      const tick = setInterval(() => {
        tries += 1;
        if ((om.child_values || []).length) { clearInterval(tick); return pick(); }
        if (tries === 4 && om.get_orders) om.get_orders();
        if (tries > 16) {
          clearInterval(tick);
          // still nothing loaded: the server decides — a party here means keep waiting, none means seat
          frappe.call("restaurant_management.house.parties", { table }).then(({ message }) => {
            if (!(message || []).length) return this.open_for(table, om, then);
            let more = 0;
            const again = setInterval(() => {
              more += 1;
              if ((om.child_values || []).length) { clearInterval(again); pick(); }
              else if (more > 20) { clearInterval(again); this.open_for(table, om, then); }
            }, 250);
          });
        }
      }, 250);
    },

    // The pad's + and a dish tapped with no check selected come here: another
    // party at this table, through the same door — PIN, covers, seats left.
    open_for(table, om, then) {
      this.__for = { table, om, then };
      return this.open();
    },

    open() {
      // Seating belongs to a waiter: the PIN is confirmed before the dialog opens,
      // so on a shared tablet the seat is credited to the person actually seating.
      if (window.RM_waiter && RM_waiter.confirm && !this.__confirmed) {
        return RM_waiter.confirm("seat").then(() => { this.__confirmed = true; this.open(); this.__confirmed = false; });
      }
      const for_table = this.__for; this.__for = null;
      const dialog = new frappe.ui.Dialog({
        title: for_table ? __("Seat another party at {0}", [for_table.table]) : __("Seat a guest"),
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
          {
            fieldname: "table", fieldtype: "Select", label: __("Table"), reqd: 1,
            change: () => toggle_address(dialog),
          },
          { fieldname: "address", fieldtype: "Small Text", label: __("Delivery address / directions"), hidden: 1 },
          { fieldname: "hint", fieldtype: "HTML" },
        ],
        primary_action_label: __("Seat & open order"),
        primary_action: (values) => seat(values, dialog),
      });
      if (for_table) { dialog.__only_table = for_table.table; dialog.__om = for_table.om; dialog.__then = for_table.then; }
      dialog.show();
      free_tables(dialog);
    },
  };
})();
