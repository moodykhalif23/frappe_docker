
// Seats, not tables. A six-top with two guests on it has four seats to sell,
// and each party on it keeps its own waiter.
(() => {
  if (window.RM_seats) return;

  const call = (m, args) => frappe.call("restaurant_management.house." + m, args || {}).then(r => r.message);

  const party_badge = (p) => {
    const who = p.initials || (p.unseated ? "?" : "");
    const title = `${p.guest} · ${p.covers || "?"} ${__("covers")}${p.waiter ? " · " + p.waiter : ""}`;
    return `<span class="rm-party" style="background-color:${p.colour}" title="${frappe.utils.escape_html(title)}">${
      frappe.utils.escape_html(who)}<i>${p.covers || "?"}</i></span>`;
  };

  window.RM_seats = {
    map: {},
    mounted: false,
    timer: null,

    mount(rm) {
      if (this.mounted) return;
      this.mounted = true;
      // The floor is still wiring itself up; do not compete with it.
      setTimeout(() => RM_seats.refresh(), 1500);
      this.timer = setInterval(() => RM_seats.refresh(), 10000);
      // Checks moving usually means seats moved with them.
      frappe.realtime.on("synchronize_order_data", () => RM_seats.soon());
    },

    soon() {
      clearTimeout(this.pending);
      this.pending = setTimeout(() => RM_seats.refresh(), 800);
    },

    seats(table) {
      return this.map[table] || null;
    },

    refresh() {
      return call("table_occupancy").then((m) => {
        RM_seats.map = m || {};
        RM_seats.paint();
        return RM_seats.map;
      });
    },

    paint() {
      Object.keys(this.map).forEach((name) => RM_seats.paint_table(name));
    },

    paint_table(name) {
      const seats = this.map[name];
      const obj = window.RM && RM.object && RM.object(name);
      if (!seats || !obj || !obj.obj || !obj.obj.obj) return;

      if (obj.no_of_seats && seats.capacity) {
        obj.no_of_seats.val(seats.occupied ? `${seats.occupied}/${seats.capacity}` : seats.capacity);
      }

      const el = $(obj.obj.obj);
      el.toggleClass("rm-full", seats.free === 0 && !!seats.capacity);
      el.toggleClass("rm-shared", seats.parties.length > 1);

      const box = el.find(".resize-handle-container").first();
      if (!box.length) return;
      box.find(".rm-party-badges").remove();
      // The section badge is whose table it is; the party badges are who is on it.
      el.find(".d-waiter-badge").toggle(!seats.parties.length);
      if (!seats.parties.length) return;
      box.append(`<span class="rm-party-badges">${seats.parties.map(party_badge).join("")}</span>`);
    },

    pick_check(om, done) {
      const orders = om.child_values || [];
      if (!orders.length) return false;
      if (orders.length === 1) {
        orders[0].select();
        setTimeout(done, 300);
        return true;
      }

      call("parties", { table: om.table.data.name }).then((parties) => {
        const by_order = {};
        (parties || []).forEach((p) => { if (p.order) by_order[p.order] = p; });

        const d = new frappe.ui.Dialog({
          title: __("Whose check is this?"),
          fields: [{
            fieldname: "order", fieldtype: "Select", label: __("Party"), reqd: 1,
            options: orders.map((o) => {
              const p = by_order[o.data.name];
              return {
                value: o.data.name,
                label: p
                  ? `${p.guest} · ${p.covers} ${__("covers")}${p.initials ? " · " + p.initials : ""}`
                  : (o.data.customer || o.data.short_name),
              };
            }),
          }],
          primary_action_label: __("Open"),
          primary_action: ({ order }) => {
            d.hide();
            const chosen = om.get_order(order);
            if (chosen) {
              chosen.select();
              setTimeout(done, 300);
            }
          },
        });
        d.show();
      });
      return true;
    },
  };
})();
