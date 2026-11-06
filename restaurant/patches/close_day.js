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
  const tillRead = (r) => !r.is_cash && (r.opening || r.sales || r.withdrawn || r.spent);
  const countDrawer = (profile) => call("day_float", { pos_profile: profile || "" }).then((rows) => {
    if (!rows || !rows.length) return {};
    const taken = [].concat(...rows.map((r) => (r.withdrawals || []).map((w) =>
      `<li>${frappe.utils.escape_html(r.mode_of_payment)} · ${w.at} · ${frappe.utils.escape_html(w.reference)} · ${format_currency(w.amount)}</li>`)));
    const list = taken.length
      ? `<div class="small" style="margin:6px 0"><b>${__("Withdrawals recorded this shift")}</b><ul style="margin:4px 0 0 18px">${taken.join("")}</ul></div>` : "";
    // rm_kitchen_stock: kitchen buys paid out of a till come off it too
    const bought = [].concat(...rows.map((r) => (r.purchases || []).map((p) =>
      `<li>${frappe.utils.escape_html(r.mode_of_payment)} · ${p.at} · ${frappe.utils.escape_html(p.note || p.name)} · ${format_currency(p.amount)}</li>`)));
    const buys = bought.length
      ? `<div class="small" style="margin:6px 0"><b>${__("Purchases paid this shift")}</b><ul style="margin:4px 0 0 18px">${bought.join("")}</ul></div>` : "";
    const less = (r) => (r.withdrawn ? " " + __("− withdrawals {0}", [format_currency(r.withdrawn)]) : "") +
      (r.spent ? " " + __("− purchases {0}", [format_currency(r.spent)]) : "");
    return new Promise((resolve) => {
      const d = new frappe.ui.Dialog({
        title: __("Count the drawer"),
        fields: [{ fieldtype: "HTML", fieldname: "intro", options:
          `<p class="text-muted small">${__("Type what you actually counted, and read the M-Pesa balance off the till. The difference is recorded on the closing entry.")}</p>` +
          list + buys + `<p><button class="btn btn-xs btn-default rm-tw-add">${__("+ Record a withdrawal first")}</button>
            <button class="btn btn-xs btn-default rm-ks-buy">${__("+ Record a purchase first")}</button></p>` }]
          // indexed, not scrubbed: frappe.scrub("M-Pesa") keeps the hyphen
          .concat(rows.map((r, i) => (tillRead(r) ? {
            fieldname: `m_${i}`, fieldtype: "Currency", reqd: 1,
            label: __("{0} balance now — read it off the till", [r.mode_of_payment]),
            description: __("opening {0} + sales {1}{2} = expected {3}", [format_currency(r.opening),
              format_currency(r.sales), less(r), format_currency(r.expected)]),
          } : {
            fieldname: `m_${i}`, fieldtype: "Currency",
            label: __("{0} — expected {1}", [r.mode_of_payment, format_currency(r.expected)]),
            description: __("float {0} + sales {1}{2}", [format_currency(r.opening), format_currency(r.sales), less(r)]),
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
      d.$wrapper.find(".rm-ks-buy").on("click", (e) => {
        e.preventDefault();
        d.hide();
        RM_kitchen.purchase().then(() => countDrawer(profile)).then(resolve);
      });
      d.show();
    });
  });

  // rm_closing_once: the screen is frozen while the close runs, and a second
  // press in that time does nothing; the server refuses a second closing anyway.
  let closing = false;
  const doClose = (profile, force) =>
    countDrawer(profile).then((counted) => {
      if (counted === null || closing) return null;
      closing = true;
      return new Promise((resolve) => frappe.call({
        method: "restaurant_management.house.close_day",
        args: { pos_profile: profile || "", force: force ? 1 : 0, counted: JSON.stringify(counted) },
        freeze: true,
        freeze_message: __("Closing the day…"),
        callback: (r) => resolve(r.message),
        always: () => { closing = false; resolve(null); },
      }));
    })
      .then((res) => {
        if (res === null) return;
        if (!res || !res.closed) {
          frappe.show_alert({ message: __("The counter was already closed"), indicator: "blue" });
          return;
        }
        if (res.already) {
          frappe.msgprint({
            title: __("Day closed"),
            indicator: "green",
            message: __("{0} had already banked this day. Its books are now posted; nothing was banked twice.", [res.closed]),
          });
          RM_close_day.badge();
          window.RM_seats && RM_seats.refresh();
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

  // rm_kitchen_stock: the kitchen's paper sheet — Opening, Add, Sold, Staff, Discard,
  // Closing — kept from the till. Sold comes off by itself with every paid bill;
  // Add is a purchase, Staff and Discard are recorded here, Closing is the count.
  const INV = "restaurant_management.inventory.";
  const inv = (m, args, freeze) => new Promise((resolve) => frappe.call({
    method: INV + m, args: args || {}, freeze: !!freeze,
    callback: (r) => resolve(r.message),
    always: () => resolve(null),
  }));
  const qtyFmt = (n) => frappe.format(n || 0, { fieldtype: "Float", precision: 2 });
  const esc = (t) => frappe.utils.escape_html(t === null || t === undefined ? "" : String(t));

  // A list built a line at a time: pick the item, say how much, + Add; Save sends every line.
  const lineDialog = ({ title, items, unitsOf, money, extra, saveLabel, save }) => new Promise((resolve) => {
    const byCode = {};
    items.forEach((i) => { byCode[i.name] = i; });
    const lines = [];
    let setUnits = () => {};
    const d = new frappe.ui.Dialog({
      title,
      size: "large",
      fields: [
        { fieldname: "item", fieldtype: "Autocomplete", label: __("Item"),
          options: items.map((i) => ({ label: i.item_name, value: i.name })),
          onchange: () => setUnits() },
        { fieldname: "c1", fieldtype: "Column Break" },
        { fieldname: "qty", fieldtype: "Float", label: __("How many") },
        { fieldname: "c2", fieldtype: "Column Break" },
        { fieldname: "uom", fieldtype: "Select", label: __("Unit") },
      ].concat(money ? [{ fieldname: "c3", fieldtype: "Column Break" },
                        { fieldname: "amount", fieldtype: "Currency", label: __("Amount paid") }] : [])
        .concat([
          { fieldname: "s1", fieldtype: "Section Break" },
          { fieldname: "add", fieldtype: "Button", label: __("+ Add to the list"), click: () => addLine() },
          { fieldname: "list", fieldtype: "HTML" },
          { fieldname: "s2", fieldtype: "Section Break" },
        ]).concat(extra),
      primary_action_label: saveLabel,
      primary_action: (v) => {
        // a line typed but never added still counts
        if (v.item && flt(v.qty) > 0 && !addLine()) return;
        if (!lines.length) { frappe.msgprint(__("Add at least one item.")); return; }
        save(lines, v).then((r) => { if (!r) return; d.hide(); resolve(r); });
      },
      secondary_action_label: __("Cancel"),
      secondary_action: () => { d.hide(); resolve(null); },
    });
    setUnits = () => {
      const it = byCode[d.get_value("item")];
      const units = it ? unitsOf(it) : [];
      d.set_df_property("uom", "options", units.map((u) => u.uom).join("\n"));
      d.set_value("uom", units.length ? units[0].uom : "");
      // the yield, so a cashier sees what a kilo becomes
      d.set_df_property("uom", "description", it ? units.filter((u) => u.factor !== 1)
        .map((u) => __("1 {0} = {1} {2}", [u.uom, qtyFmt(u.factor), it.stock_uom])).join(" · ") : "");
    };
    const render = () => {
      const total = lines.reduce((a, l) => a + (l.amount || 0), 0);
      const $w = d.fields_dict.list.$wrapper;
      $w.html(lines.length
        ? `<table class="table table-sm small" style="margin:6px 0"><tbody>${lines.map((l, i) =>
            `<tr><td>${esc(l.item_name)}</td><td class="text-right">${qtyFmt(l.qty)} ${esc(l.uom)}</td>` +
            (money ? `<td class="text-right">${format_currency(l.amount)}</td>` : "") +
            `<td class="text-right"><a href="#" class="rm-ks-rm" data-i="${i}">${__("remove")}</a></td></tr>`).join("")}</tbody></table>` +
          (money ? `<p class="small"><b>${__("Total")} ${format_currency(total)}</b></p>` : "")
        : `<p class="text-muted small">${__("Pick an item, say how much, then + Add to the list. Save when the list is complete.")}</p>`);
      $w.find(".rm-ks-rm").on("click", (e) => {
        e.preventDefault();
        lines.splice(Number($(e.currentTarget).attr("data-i")), 1);
        render();
      });
    };
    const addLine = () => {
      const v = d.get_values(true) || {};
      const it = byCode[v.item];
      if (!it || !(flt(v.qty) > 0)) {
        frappe.show_alert({ message: __("Pick an item and how many."), indicator: "orange" });
        return false;
      }
      lines.push({ item_code: it.name, item_name: it.item_name, qty: flt(v.qty),
                   uom: v.uom || it.stock_uom, amount: money ? flt(v.amount) : 0 });
      d.set_value("item", "");
      d.set_value("qty", null);
      if (money) d.set_value("amount", null);
      render();
      return true;
    };
    d.show();
    render();
  });

  window.RM_kitchen = {
    purchase() {
      return inv("buyable").then((items) => {
        if (!items || !items.length) {
          frappe.msgprint(__("No kitchen items are set up yet."));
          return null;
        }
        return lineDialog({
          title: __("Record a purchase"),
          items,
          money: true,
          unitsOf: (it) => it.units || [{ uom: it.stock_uom, factor: 1 }],
          extra: [
            { fieldname: "paid_from", fieldtype: "Select", label: __("Paid from"), options: "Cash\nM-Pesa", default: "Cash" },
            { fieldname: "c4", fieldtype: "Column Break" },
            { fieldname: "note", fieldtype: "Data", label: __("Note"), description: __("Where it was bought, receipt number") },
          ],
          saveLabel: __("Save purchase"),
          save: (lines, v) => inv("record_purchase",
            { lines: JSON.stringify(lines), paid_from: v.paid_from, note: v.note || "" }, true).then((r) => {
            if (r) {
              frappe.show_alert({ message: __("Recorded {0} for {1} item(s), paid from {2}. It comes off what {2} should hold.",
                [format_currency(r.total), r.lines, r.paid_from]), indicator: "green" }, 8);
            }
            return r;
          }),
        });
      });
    },

    use() {
      return inv("kitchen_items").then((items) => {
        if (!items || !items.length) {
          frappe.msgprint(__("No kitchen items are set up yet."));
          return null;
        }
        return lineDialog({
          title: __("Staff meal / discard"),
          items,
          money: false,
          unitsOf: (it) => [{ uom: it.stock_uom, factor: 1 }],
          extra: [
            { fieldname: "kind", fieldtype: "Select", label: __("What happened"), options: "Staff\nDiscard", default: "Staff",
              description: __("Staff: eaten by staff. Discard: thrown away.") },
            { fieldname: "c4", fieldtype: "Column Break" },
            { fieldname: "reason", fieldtype: "Data", label: __("Why"),
              description: __("Needed for a discard: spoiled, burnt, dropped…") },
          ],
          saveLabel: __("Save"),
          save: (lines, v) => inv("record_kitchen_use",
            { lines: JSON.stringify(lines), kind: v.kind, reason: v.reason || "" }, true).then((r) => {
            if (r) {
              frappe.show_alert({ message: v.kind === "Staff"
                ? __("Recorded {0} item(s) as staff meals.", [r.lines])
                : __("Recorded {0} item(s) as discarded.", [r.lines]), indicator: "green" }, 6);
            }
            return r;
          }),
        });
      });
    },

    sheet(day) {
      return inv("stock_sheet", { day: day || "" }).then((s) => {
        if (!s) return;
        if (!s.rows.length) {
          frappe.msgprint(__("No kitchen items are set up yet."));
          return;
        }
        // nothing in the ledger yet: this first count becomes the opening stock
        const first = !s.rows.some((r) => r.opening || r.add || r.sold || r.staff || r.discard || r.other);
        const n = (x) => (x ? qtyFmt(x) : "");
        const head = [__("Item"), __("Opening"), __("Add"), __("Sold"), __("Staff"), __("Discard"),
                      __("Should be left"), __("Counted"), __("Difference")];
        const body = s.rows.map((r) => `<tr><td>${esc(r.item_name)} <span class="text-muted">${esc(r.uom)}</span></td>` +
          `<td class="text-right">${n(r.opening)}</td><td class="text-right">${n(r.add)}</td>` +
          `<td class="text-right">${n(r.sold)}</td><td class="text-right">${n(r.staff)}</td>` +
          `<td class="text-right">${n(r.discard)}</td><td class="text-right"><b>${qtyFmt(r.expected)}</b></td>` +
          `<td style="width:96px"><input type="number" min="0" step="0.25" class="form-control input-xs rm-ks-count"` +
          ` data-code="${esc(r.item_code)}" value="${r.counted === null ? "" : r.counted}"></td>` +
          `<td class="text-right${r.difference < 0 ? " text-danger" : ""}">${r.difference === null ? "" : qtyFmt(r.difference)}</td></tr>`).join("");
        const d = new frappe.ui.Dialog({
          title: __("Kitchen stock — {0}", [frappe.datetime.str_to_user(s.day)]),
          size: "extra-large",
          fields: [{ fieldtype: "HTML", fieldname: "sheet", options:
            `<p class="text-muted small">${s.from
              ? __("Sold comes off with every paid bill. Type what is really left in Counted, then save the count.")
              : __("Bills are not taking stock off yet: Restaurant Settings › Kitchen stock from is blank.")}</p>` +
            `<div style="overflow-x:auto"><table class="table table-sm table-bordered small"><thead><tr>${
              head.map((h, i) => `<th${i ? ' class="text-right"' : ""}>${h}</th>`).join("")}</tr></thead><tbody>${body}</tbody></table></div>` +
            (first ? `<p class="small text-warning">${__("Nothing is in the books yet: this first count becomes the opening stock.")}</p>` : "") }],
          primary_action_label: __("Save the count"),
          primary_action: () => {
            const counts = {};
            d.$wrapper.find(".rm-ks-count").each((i, el) => {
              if (el.value !== "") counts[$(el).attr("data-code")] = flt(el.value);
            });
            if (!Object.keys(counts).length) {
              frappe.msgprint(__("Type at least one count."));
              return;
            }
            inv("record_count", { counts: JSON.stringify(counts), opening: first ? 1 : 0 }, true).then((r) => {
              if (!r) return;
              d.hide();
              frappe.show_alert({ message: r.changed ? __("Count saved: {0} item(s) adjusted.", [r.changed])
                : __("Count saved: everything matched."), indicator: "green" }, 6);
              RM_kitchen.sheet(s.day);
            });
          },
          secondary_action_label: __("Close"),
          secondary_action: () => d.hide(),
        });
        d.show();
      });
    },
    setup() {
      return inv("kitchen_setup").then((k) => {
        if (!k) return;
        const d = new frappe.ui.Dialog({
          title: __("Kitchen setup"),
          size: "extra-large",
          fields: [
            { fieldtype: "HTML", options: `<p class="text-muted small">${__("What the kitchen counts. Each item is counted in one unit (portions or pieces) and bought in another: say how many one bought unit gives, e.g. 1 Kg of beef gives 6 Portion. A new number counts for every purchase from now on.")}</p>` },
            { fieldname: "items", fieldtype: "Table", label: __("Kitchen stock items"), in_place_edit: true,
              data: k.items.map((i) => ({ code: i.code, item_name: i.item_name, stock_uom: i.stock_uom,
                                          bought_in: i.bought_in, per: i.per, cost: i.cost, active: i.active })),
              fields: [
                { fieldname: "item_name", fieldtype: "Data", label: __("Item"), in_list_view: 1, reqd: 1, columns: 3 },
                { fieldname: "stock_uom", fieldtype: "Link", options: "UOM", label: __("Counted in"), in_list_view: 1, columns: 2, default: "Portion" },
                { fieldname: "bought_in", fieldtype: "Link", options: "UOM", label: __("Bought in"), in_list_view: 1, columns: 2 },
                { fieldname: "per", fieldtype: "Float", label: __("One gives"), in_list_view: 1, columns: 1 },
                { fieldname: "cost", fieldtype: "Currency", label: __("Cost each"), in_list_view: 1, columns: 1,
                  description: __("What one bought unit costs") },
                { fieldname: "active", fieldtype: "Check", label: __("Active"), in_list_view: 1, columns: 1, default: 1 },
                { fieldname: "code", fieldtype: "Data", label: __("Code"), read_only: 1 },
              ] },
            { fieldname: "expenses", fieldtype: "Table", label: __("Kitchen expenses (bought at the till, not counted)"), in_place_edit: true,
              data: (k.expenses || []).map((e) => ({ code: e.code, item_name: e.item_name, stock_uom: e.stock_uom,
                                                     account: e.account, active: e.active })),
              fields: [
                { fieldname: "item_name", fieldtype: "Data", label: __("Item"), in_list_view: 1, reqd: 1, columns: 4 },
                { fieldname: "stock_uom", fieldtype: "Link", options: "UOM", label: __("Unit"), in_list_view: 1, columns: 2, default: "Unit" },
                { fieldname: "account", fieldtype: "Link", options: "Account", label: __("Booked to"), in_list_view: 1, columns: 3,
                  get_query: () => ({ filters: { root_type: "Expense", is_group: 0 } }) },
                { fieldname: "active", fieldtype: "Check", label: __("Active"), in_list_view: 1, columns: 1, default: 1 },
                { fieldname: "code", fieldtype: "Data", label: __("Code"), read_only: 1 },
              ] },
            { fieldtype: "Section Break" },
            { fieldtype: "HTML", options: `<p class="text-muted small">${__("What ONE of each dish takes from kitchen stock. A dish that takes from two items gets two lines; a dish with no line takes nothing. Save new items first, then pick them here.")}</p>` },
            { fieldname: "uses", fieldtype: "Table", label: __("Dishes"), in_place_edit: true,
              data: k.uses.map((u) => ({ dish: u.dish, stock_item: u.stock_item, portions: u.portions })),
              fields: [
                { fieldname: "dish", fieldtype: "Link", options: "Item", label: __("Dish"), in_list_view: 1, reqd: 1, columns: 4,
                  get_query: () => ({ filters: { name: ["in", k.dishes] } }) },
                { fieldname: "stock_item", fieldtype: "Link", options: "Item", label: __("Takes"), in_list_view: 1, reqd: 1, columns: 4,
                  get_query: () => ({ filters: { item_group: k.stock_group, is_stock_item: 1, disabled: 0 } }) },
                { fieldname: "portions", fieldtype: "Float", label: __("How many"), in_list_view: 1, reqd: 1, columns: 2, default: 1 },
              ] },
            { fieldtype: "HTML", options: `<p class="small"><a href="/app/restaurant-settings" target="_blank">${__("More kitchen stock settings: start date, when stock comes off, accounts")}</a></p>` },
          ],
          primary_action_label: __("Save"),
          primary_action: (v) => {
            const items = (v.items || []).filter((r) => r.item_name);
            const uses = (v.uses || []).filter((r) => r.dish);
            // every dish that had lines or has them now: a dish whose lines were removed is cleared
            const dishes = [...new Set(k.uses.map((u) => u.dish).concat(uses.map((u) => u.dish)))];
            const expenses = (v.expenses || []).filter((r) => r.item_name);
            inv("save_kitchen_items", { rows: JSON.stringify(items) }, true)
              .then((r) => r && inv("save_expense_items", { rows: JSON.stringify(expenses) }, true))
              .then((r) => r && inv("save_dish_uses", { rows: JSON.stringify(uses), dishes: JSON.stringify(dishes) }, true))
              .then((r) => {
                if (!r) return;
                d.hide();
                frappe.show_alert({ message: __("Kitchen setup saved."), indicator: "green" }, 5);
              });
          },
          secondary_action_label: __("Cancel"),
          secondary_action: () => d.hide(),
        });
        d.show();
      });
    },
  };

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
            `<p><button class="btn btn-sm btn-default rm-tw-add">${__("Record a till withdrawal")}</button>
              <button class="btn btn-sm btn-default rm-ks-buy">${__("Record a purchase")}</button>
              <button class="btn btn-sm btn-default rm-ks-use">${__("Staff meal / discard")}</button>
              <button class="btn btn-sm btn-default rm-ks-sheet">${__("Kitchen stock sheet")}</button>
              ${frappe.user.has_role(["Restaurant Manager", "System Manager", "Accounts Manager"])
                ? `<button class="btn btn-sm btn-default rm-ks-setup">${__("Kitchen setup")}</button>` : ""}</p>` }],
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
        // rm_kitchen_stock: the kitchen's paper sheet, kept from the till
        d.$wrapper.find(".rm-ks-buy").on("click", (e) => { e.preventDefault(); d.hide(); RM_kitchen.purchase(); });
        d.$wrapper.find(".rm-ks-use").on("click", (e) => { e.preventDefault(); d.hide(); RM_kitchen.use(); });
        d.$wrapper.find(".rm-ks-sheet").on("click", (e) => { e.preventDefault(); d.hide(); RM_kitchen.sheet(); });
        d.$wrapper.find(".rm-ks-setup").on("click", (e) => { e.preventDefault(); d.hide(); RM_kitchen.setup(); });
        d.show();
      });
    },
  };
})();
