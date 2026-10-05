// Opening and closing the selling day from the floor. A shift left open bills
(() => {
  if (window.RM_close_day) return;

  const call = (m, args) => frappe.call("restaurant_management.house." + m, args || {}).then(r => r.message);
  const money = (n, c) => `${c || ""} ${frappe.format(n || 0, { fieldtype: "Float", precision: 2 })}`.trim();

  // rm_till_withdrawals: record money an owner took out of a till, from the till
  // itself. The phone page (/till-withdrawal) does the same for the owners.
  const TW = "restaurant_management.restaurant_management.doctype.till_withdrawal.till_withdrawal.";
  const recordWithdrawal = () => new Promise((resolve) => {
    const d = new frappe.ui.Dialog({
      title: __("Record a till withdrawal"),
      fields: [
        { fieldname: "sms_text", fieldtype: "Small Text", label: __("Paste the M-Pesa SMS"),
          description: __("The code, amount, time and charge are read from it."),
          onchange: () => {
            const sms = d.get_value("sms_text");
            if (!sms) return;
            frappe.call(TW + "preview", { sms_text: sms }).then(({ message: p }) => {
              if (!p) return;
              ["reference", "amount", "withdrawn_at", "transaction_cost"].forEach((f) => {
                if (p[f] !== null && p[f] !== undefined && p[f] !== "") d.set_value(f, p[f]);
              });
              d.fields_dict.warn.$wrapper.html((p.warnings || []).map((w) =>
                `<p class="text-warning small">${frappe.utils.escape_html(w)}</p>`).join(""));
            });
          } },
        { fieldname: "warn", fieldtype: "HTML" },
        { fieldname: "mode_of_payment", fieldtype: "Select", label: __("From"), options: "M-Pesa\nCash", default: "M-Pesa" },
        { fieldname: "amount", fieldtype: "Currency", label: __("Amount withdrawn"), reqd: 1 },
        { fieldname: "reference", fieldtype: "Data", label: __("M-Pesa code"), reqd: 1 },
        { fieldname: "cb", fieldtype: "Column Break" },
        { fieldname: "withdrawn_at", fieldtype: "Datetime", label: __("When"), reqd: 1,
          default: frappe.datetime.now_datetime() },
        { fieldname: "transaction_cost", fieldtype: "Currency", label: __("Safaricom charge"), default: 0 },
        { fieldname: "withdrawn_by", fieldtype: "Data", label: __("Withdrawn by") },
        { fieldname: "note", fieldtype: "Small Text", label: __("Note") },
      ],
      primary_action_label: __("Record withdrawal"),
      primary_action: (v) => {
        frappe.call({ method: TW + "record", args: v, freeze: true }).then(({ message: r }) => {
          if (!r) return;
          d.hide();
          frappe.show_alert({ message: __("Recorded {0} ({1}). It comes off the expected balance.",
            [format_currency(flt(r.amount) + flt(r.transaction_cost)), r.reference]), indicator: "green" }, 8);
          resolve(r);
        });
      },
      secondary_action_label: __("Cancel"),
      secondary_action: () => { d.hide(); resolve(null); },
    });
    d.show();
  });

  // Ask what is actually in the drawer before banking, or the closing entry
  // records a guess. rm_till_withdrawals: the M-Pesa till is a balance READ off the
  // phone, never pre-filled — a pre-filled expected figure is why every close came
  // out exact while what the owners withdrew surfaced as a mystery drop in the next
  // morning's opening balance.
  const tillRead = (r) => !r.is_cash && (r.opening || r.sales || r.withdrawn);
  const countDrawer = (profile) => call("day_float", { pos_profile: profile || "" }).then((rows) => {
    if (!rows || !rows.length) return {};
    const taken = [].concat(...rows.map((r) => (r.withdrawals || []).map((w) =>
      `<li>${frappe.utils.escape_html(r.mode_of_payment)} · ${w.at} · ${frappe.utils.escape_html(w.reference)} · ${format_currency(w.amount)}</li>`)));
    const list = taken.length
      ? `<div class="small" style="margin:6px 0"><b>${__("Withdrawals recorded this shift")}</b><ul style="margin:4px 0 0 18px">${taken.join("")}</ul></div>` : "";
    return new Promise((resolve) => {
      const d = new frappe.ui.Dialog({
        title: __("Count the drawer"),
        fields: [{ fieldtype: "HTML", fieldname: "intro", options:
          `<p class="text-muted small">${__("Type what you actually counted, and read the M-Pesa balance off the till. The difference is recorded on the closing entry.")}</p>` +
          list + `<p><button class="btn btn-xs btn-default rm-tw-add">${__("+ Record a withdrawal first")}</button></p>` }]
          // indexed, not scrubbed: frappe.scrub("M-Pesa") keeps the hyphen
          .concat(rows.map((r, i) => (tillRead(r) ? {
            fieldname: `m_${i}`, fieldtype: "Currency", reqd: 1,
            label: __("{0} balance now — read it off the till", [r.mode_of_payment]),
            description: __("opening {0} + sales {1} − withdrawals {2} = expected {3}", [format_currency(r.opening),
              format_currency(r.sales), format_currency(r.withdrawn || 0), format_currency(r.expected)]),
          } : {
            fieldname: `m_${i}`, fieldtype: "Currency",
            label: __("{0} — expected {1}", [r.mode_of_payment, format_currency(r.expected)]),
            description: r.withdrawn
              ? __("float {0} + sales {1} − withdrawals {2}", [format_currency(r.opening), format_currency(r.sales), format_currency(r.withdrawn)])
              : __("float {0} + sales {1}", [format_currency(r.opening), format_currency(r.sales)]),
            default: r.is_cash ? r.expected : null,
          }))),
        primary_action_label: __("Bank it"),
        primary_action: (v) => {
          d.hide();
          const counted = {};
          rows.forEach((r, i) => {
            const val = v[`m_${i}`];
            // blank is "not counted" (null), never zero
            counted[r.mode_of_payment] = (val === undefined || val === null || val === "") ? null : flt(val);
          });
          resolve(counted);
        },
        secondary_action_label: __("Cancel"),
        secondary_action: () => { d.hide(); resolve(null); },
      });
      d.$wrapper.find(".rm-tw-add").on("click", (e) => {
        e.preventDefault();
        d.hide();
        recordWithdrawal().then(() => countDrawer(profile)).then(resolve);
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
    withdrawal: recordWithdrawal,  // rm_till_withdrawals

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
                __("Count the cash into the drawer and read the till balance off the phone, then open. Nothing can be billed until you do.")}</p>` },
            ].concat(f.modes.map((m, i) => {
              // cash sits in a drawer and is counted; M-Pesa is a balance that is read
              const isCash = (f.cash_modes || []).includes(m);
              return {
                fieldname: `mode_${i}`, fieldtype: "Currency",
                label: isCash ? __("{0} float", [m]) : __("{0} opening balance", [m]),
                default: 0,
                description: isCash ? __("Counted into the drawer, not guessed")
                                    : __("What the till shows before service"),
              };
            })),
            primary_action_label: __("Open the day"),
            primary_action: (values) => {
              const balances = {};
              f.modes.forEach((m, i) => { balances[m] = values[`mode_${i}`] || 0; });
              d.hide();
              call("open_day", { pos_profile: f.profile, balances: JSON.stringify(balances) })
                .then((res) => {
                  if (!res) return;
                  // rm_till_withdrawals: a till that opens lower than it closed
                  const gaps = (res.gaps || []).map((g) => g.unexplained < 0
                    ? __("<b>{0} opened {1} lower than it closed</b> (closed {2}, opened {3}, withdrawals recorded {4}). If an owner withdrew it, record it now: Day › Record a till withdrawal.",
                        [frappe.utils.escape_html(g.mode_of_payment), format_currency(-g.unexplained), format_currency(g.closed_at), format_currency(g.opening), format_currency(g.recorded)])
                    : __("<b>{0} opened {1} higher than it closed</b> (closed {2}, opened {3}). Money came in outside the till.",
                        [frappe.utils.escape_html(g.mode_of_payment), format_currency(g.unexplained), format_currency(g.closed_at), format_currency(g.opening)]));
                  frappe.msgprint({
                    title: res.opened ? __("Day open") : __("Already open"),
                    indicator: gaps.length ? "orange" : "green",
                    message: (res.opened
                      ? __("Shift {0} is open with a float of {1}.", [res.opened, money(res.float, res.currency)])
                      : __("The counter is already open.")) + gaps.map((g) => `<br><br>${g}`).join(""),
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
          fields: [{ fieldtype: "HTML", options: `<div class="rm-close-day">${lines.map(l => `<p>${l}</p>`).join("")}</div>` +
            `<p><button class="btn btn-sm btn-default rm-tw-add">${__("Record a till withdrawal")}</button></p>` }],
          primary_action_label: s.open_checks ? __("Close anyway") : __("Close the day"),
          primary_action: () => {
            d.hide();
            doClose(profile, s.open_checks ? 1 : 0);
          },
          secondary_action_label: __("Keep it open"),
          secondary_action: () => d.hide(),
        });
        // rm_till_withdrawals: no sixth toolbar button — it lives behind Day
        d.$wrapper.find(".rm-tw-add").on("click", (e) => { e.preventDefault(); d.hide(); recordWithdrawal(); });
        d.show();
      });
    },
  };
})();
