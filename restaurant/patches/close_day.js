// Opening and closing the selling day from the floor. A shift left open bills
(() => {
  if (window.RM_close_day) return;

  const call = (m, args) => frappe.call("restaurant_management.house." + m, args || {}).then(r => r.message);
  const money = (n, c) => `${c || ""} ${frappe.format(n || 0, { fieldtype: "Float", precision: 2 })}`.trim();

  // Ask what is actually in the drawer before banking, or the closing entry
  const countDrawer = (profile) => call("day_float", { pos_profile: profile || "" }).then((rows) => {
    if (!rows || !rows.length) return {};
    return new Promise((resolve) => {
      const d = new frappe.ui.Dialog({
        title: __("Count the drawer"),
        fields: [{ fieldtype: "HTML", options:
          `<p class="text-muted small">${__("Type what you actually counted. The difference is recorded on the closing entry.")}</p>` }]
          // indexed, not scrubbed: frappe.scrub("M-Pesa") keeps the hyphen
          .concat(rows.map((r, i) => ({
            fieldname: `m_${i}`, fieldtype: "Currency",
            label: __("{0} — expected {1}", [r.mode_of_payment, format_currency(r.expected)]),
            description: __("float {0} + sales {1}", [format_currency(r.opening), format_currency(r.sales)]),
            default: r.expected,
          }))),
        primary_action_label: __("Bank it"),
        primary_action: (v) => {
          d.hide();
          const counted = {};
          rows.forEach((r, i) => { counted[r.mode_of_payment] = flt(v[`m_${i}`]); });
          resolve(counted);
        },
        secondary_action_label: __("Cancel"),
        secondary_action: () => { d.hide(); resolve(null); },
      });
      d.show();
    });
  });

  const doClose = (profile, force) =>
    countDrawer(profile).then((counted) => {
      if (counted === null) return null;
      return call("close_day", { pos_profile: profile || "", force: force ? 1 : 0,
                                 counted: JSON.stringify(counted) });
    })
      .then((res) => {
        if (res === null) return;
        if (!res || !res.closed) {
          frappe.show_alert({ message: __("The counter was already closed"), indicator: "blue" });
          return;
        }
        // an unpaid check is never voided by the close: name each one, or the
        const left = res.open_checks_detail || [];
        const standing = left.length ? "<br><br>" + __("{0} unpaid check(s) still open:", [left.length]) + "<ul style='margin:6px 0 0 18px'>" +
          left.map(c => `<li><b>${frappe.utils.escape_html(c.table)}</b> · ${frappe.utils.escape_html(c.customer || __("no guest name"))} · ${format_currency(c.amount)}</li>`).join("") +
          "</ul>" + __("Settle each one, or Release the table to void it.") : "";
        // a drawer that does not match what was rung is the whole point of counting it
        const off = (res.variance || []).filter(v => Math.abs(v.difference) > 0.005);
        const cash = off.length ? "<br><br>" + __("Counted against expected:") + "<ul style='margin:6px 0 0 18px'>" +
          off.map(v => `<li><b>${frappe.utils.escape_html(v.mode_of_payment)}</b> · ${__("expected")} ${format_currency(v.expected)} · ${__("counted")} ${format_currency(v.counted)} · <b>${v.difference > 0 ? __("over") : __("short")} ${format_currency(Math.abs(v.difference))}</b></li>`).join("") +
          "</ul>" : "";
        frappe.msgprint({
          title: __("Day closed"),
          indicator: (left.length || off.length) ? "orange" : "green",
          message: __("{0} banked {1} sale(s). {2} table section(s) released. Open the day again when you next serve.",
            [res.closed, res.invoices, res.sections_cleared]) + cash + standing,
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
      // One button, not two: a sixth toolbar item pushes the rest into an
      this.day_btn = rm.page.add_inner_button(__("Day"), () => {
        call("day_summary").then((s) => (s && s.open ? RM_close_day.open() : RM_close_day.open_day()));
      });
      this.badge();
    },

    button(re) {
      return $(".page-actions button").filter((i, b) => re.test($(b).text())).first();
    },

    badge() {
      call("day_summary").then((s) => {
        const btn = this.button(/^\s*(Day|Open day|Close day)/);
        if (!s || !btn.length) return;
        // A day still open from before today is the thing that breaks billing.
        btn.text(!s.open ? __("Open day")
          : s.stale ? __("Close day (yesterday)") : __("Close day"));
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
                __("Count the float into the drawer, then open. Nothing can be billed until you do.")}${
                (f.not_counted || []).length ? "<br>" + __("{0} holds no drawer float and opens at zero — do not enter a till balance here.",
                  [f.not_counted.join(", ")]) : ""}</p>` },
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
