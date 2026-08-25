// Closing the selling day from the floor. A shift left open bills into
// yesterday and then refuses today's sales, which reads as a broken till.
(() => {
  if (window.RM_close_day) return;

  const call = (m, args) => frappe.call("restaurant_management.house." + m, args || {}).then(r => r.message);
  const money = (n, c) => `${c || ""} ${frappe.format(n || 0, { fieldtype: "Float", precision: 2 })}`.trim();

  const doClose = (profile, force) =>
    call("close_day", { pos_profile: profile || "", force: force ? 1 : 0 })
      .then((res) => {
        if (!res || !res.closed) {
          frappe.show_alert({ message: __("The counter was already closed"), indicator: "blue" });
          return;
        }
        frappe.msgprint({
          title: __("Day closed"),
          indicator: "green",
          message: __("{0} banked {1} sale(s). Open a new day when you next serve.",
            [res.closed, res.invoices]),
        });
        RM_close_day.badge();
      });

  window.RM_close_day = {
    mounted: false,

    mount(rm) {
      if (this.mounted || !rm.page || !rm.page.add_inner_button) return;
      this.mounted = true;
      this.rm = rm;
      rm.page.add_inner_button(__("Close day"), () => RM_close_day.open());
      this.badge();
    },

    badge() {
      call("day_summary").then((s) => {
        const btn = $(".page-actions button").filter((i, b) => /Close day/.test($(b).text())).first();
        if (!btn.length || !s) return;
        // A day still open from before today is the thing that breaks billing.
        btn.text(s.open && s.stale ? __("Close day (yesterday)") : __("Close day"));
      });
    },

    open() {
      const profile = (window.cur_pos && cur_pos.pos_profile) || "";
      call("day_summary", { pos_profile: profile }).then((s) => {
        if (!s || !s.open) {
          frappe.msgprint({
            title: __("Nothing to close"),
            indicator: "blue",
            message: __("The counter is not open. It opens itself when the first order is rung up."),
          });
          return;
        }

        const lines = [
          __("Opened: {0}", [(s.opened_at || "").slice(0, 16)]),
          __("Sales so far: {0} over {1} bill(s)", [money(s.sales, s.currency), s.invoices]),
        ];
        if (s.stale) lines.push(`<b>${__("This day started before today.")}</b>`);
        if (s.open_checks) {
          lines.push(`<b>${__("{0} check(s) are still open, worth {1}.",
            [s.open_checks, money(s.open_checks_value, s.currency)])}</b>`);
          lines.push(__("Closing now leaves those tables with no way to bill."));
        }

        const d = new frappe.ui.Dialog({
          title: __("Close the selling day?"),
          fields: [{ fieldtype: "HTML", options: `<div class="rm-close-day">${lines.map(l => `<p>${l}</p>`).join("")}</div>` }],
          primary_action_label: s.open_checks ? __("Close anyway") : __("Close the day"),
          primary_action: () => {
            d.hide();
            doClose(profile, s.open_checks ? 1 : 0);
          },
          secondary_action_label: __("Keep it open"),
          secondary_action: () => d.hide(),
        });
        d.show();
      });
    },
  };
})();
