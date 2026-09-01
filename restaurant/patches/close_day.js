// Opening and closing the selling day from the floor. A shift left open bills
// into yesterday and then refuses today's sales, which reads as a broken till.
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
          message: __("{0} banked {1} sale(s). {2} table section(s) released. Open the day again when you next serve.",
            [res.closed, res.invoices, res.sections_cleared]),
        });
        RM_close_day.badge();
        window.RM_seats && RM_seats.refresh();
      });

  window.RM_close_day = {
    mounted: false,

    mount(rm) {
      if (this.mounted || !rm.page || !rm.page.add_inner_button) return;
      this.mounted = true;
      this.rm = rm;
      const caps = (frappe.boot && frappe.boot.user && frappe.boot.user.can_create) || [];
      if (caps.indexOf("POS Closing Entry") === -1) return;
      rm.page.add_inner_button(__("Open day"), () => RM_close_day.open_day());
      rm.page.add_inner_button(__("Close day"), () => RM_close_day.open());
      this.badge();
    },

    button(re) {
      return $(".page-actions button").filter((i, b) => re.test($(b).text())).first();
    },

    badge() {
      call("day_summary").then((s) => {
        const close = this.button(/Close day/);
        const open = this.button(/Open day/);
        if (!s) return;
        // A day still open from before today is the thing that breaks billing.
        if (close.length) close.text(s.open && s.stale ? __("Close day (yesterday)") : __("Close day")).toggle(!!s.open);
        if (open.length) open.toggle(!s.open);
      });
    },

    open_day() {
      const profile = (window.cur_pos && cur_pos.pos_profile) || "";
      call("day_summary", { pos_profile: profile }).then((s) => {
        if (s && s.open) {
          frappe.msgprint({
            title: __("Already open"),
            indicator: "blue",
            message: __("The counter has been open since {0}.", [(s.opened_at || "").slice(0, 16)]),
          });
          RM_close_day.badge();
          return;
        }

        call("opening_floats", { pos_profile: profile }).then((f) => {
          if (!f) return;
          const d = new frappe.ui.Dialog({
            title: __("Open the selling day"),
            fields: [
              { fieldtype: "HTML", options: `<p class="text-muted small">${
                __("Count the float into the drawer, then open. Nothing can be billed until you do.")}</p>` },
            ].concat(f.modes.map((m, i) => ({
              fieldname: `mode_${i}`, fieldtype: "Currency", label: __("{0} float", [m]),
              default: 0, description: i === 0 ? __("Counted, not guessed") : "",
            }))),
            primary_action_label: __("Open the day"),
            primary_action: (values) => {
              const balances = {};
              f.modes.forEach((m, i) => { balances[m] = values[`mode_${i}`] || 0; });
              d.hide();
              call("open_day", { pos_profile: f.profile, balances: JSON.stringify(balances) })
                .then((res) => {
                  if (!res) return;
                  frappe.msgprint({
                    title: res.opened ? __("Day open") : __("Already open"),
                    indicator: "green",
                    message: res.opened
                      ? __("Shift {0} is open with a float of {1}.", [res.opened, money(res.float, res.currency)])
                      : __("The counter is already open."),
                  });
                  RM_close_day.badge();
                });
            },
          });
          d.show();
        });
      });
    },

    open() {
      const profile = (window.cur_pos && cur_pos.pos_profile) || "";
      call("day_summary", { pos_profile: profile }).then((s) => {
        if (!s || !s.open) {
          frappe.msgprint({
            title: __("Nothing to close"),
            indicator: "blue",
            message: __("The counter is not open. Use Open day to start service."),
          });
          RM_close_day.badge();
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
        lines.push(__("Closing also clears every table section and closes any party still sitting."));

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
