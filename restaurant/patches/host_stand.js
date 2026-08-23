
// Host stand. The stock check-in wants an existing Customer and a reservation
// window, then hides itself with no table picked — useless for a walk-in.
(() => {
  if (window.RM_host_stand) return;

  const free_tables = (dialog) => {
    const covers = dialog.get_value("covers") || 0;
    return frappe.call("restaurant_management.house.free_tables", { covers }).then(({ message }) => {
      const tables = message || [];
      const field = dialog.get_field("table");
      field.df.options = tables.map(t => ({ value: t.name, label: `${t.description} · ${t.seats ? __("seats {0}", [t.seats]) : __("capacity not set")}` }));
      field.refresh();
      dialog.fields_dict.hint.$wrapper.html(
        tables.length
          ? `<p class="text-muted small">${__("{0} table(s) free for {1}", [tables.length, covers || __("any party")])}</p>`
          : `<p class="text-danger small">${__("No free table seats {0} — free one up or split the party.", [covers])}</p>`
      );
      if (tables.length) dialog.set_value("table", tables[0].name);
    });
  };

  const seat = (values, dialog) => {
    frappe.call({
      method: "restaurant_management.house.seat_walkin",
      args: values,
      freeze: true,
      freeze_message: __("Seating the party..."),
    }).then(({ message }) => {
      if (!message) return;
      dialog.hide();
      // The floor already knows how to jump to a table and open its order pad.
      RM.navigate_room = message.room;
      RM.navigate_table = message.table;
      frappe.set_route(`restaurant-manage?restaurant_room=${message.room}`);
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
      const dialog = new frappe.ui.Dialog({
        title: __("Seat a guest"),
        fields: [
          { fieldname: "guest_name", fieldtype: "Data", label: __("Guest name"), reqd: 1 },
          {
            fieldname: "covers", fieldtype: "Int", label: __("Guests"), default: 2, reqd: 1,
            change: () => free_tables(dialog),
          },
          { fieldname: "contact", fieldtype: "Data", label: __("Phone (optional)") },
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
