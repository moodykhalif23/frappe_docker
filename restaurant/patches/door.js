
// The door: who is waiting, who is expected, and one tap to seat them.
// A waiting party is a Restaurant Booking with no table, so seating from the
// queue is the same operation as seating a walk-in.
(() => {
  if (window.RM_door) return;

  const esc = (s) => frappe.utils.escape_html(String(s == null ? "" : s));
  const call = (m, args) => frappe.call("restaurant_management.house." + m, args || {}).then(r => r.message);

  const goToTable = (room, table) => {
    RM.navigate_table = table;
    const r = window.RM && RM.object && RM.object(room);
    if (r && r.select) return r.select();
    RM.navigate_room = room;
    frappe.set_route("restaurant-manage", { restaurant_room: room });
  };

  // Pick a table that fits, then seat the party on it.
  const seatParty = (row, dialog) => {
    call("free_tables", { covers: row.covers }).then(tables => {
      if (!tables || !tables.length) {
        frappe.msgprint({
          title: __("Nothing free yet"),
          indicator: "orange",
          message: __("No free table seats {0}. They stay at the top of the queue.", [row.covers]),
        });
        return;
      }
      const pick = new frappe.ui.Dialog({
        title: __("Seat {0} ({1})", [row.guest, row.covers]),
        fields: [{
          fieldname: "table", fieldtype: "Select", label: __("Table"), reqd: 1,
          options: tables.map(t => ({
            value: t.name,
            label: `${t.description} · ${t.seats ? __("seats {0}", [t.seats]) : __("capacity not set")}`,
          })),
          default: tables[0].name,
        }],
        primary_action_label: __("Seat & open order"),
        primary_action: ({ table }) => {
          call("seat_from_waitlist", { booking: row.name, table }).then(res => {
            pick.hide();
            dialog.hide();
            frappe.show_alert({
              message: __("{0} seated after {1} min", [row.guest, res.waited]),
              indicator: "green",
            });
            goToTable(res.room, res.table);
          });
        },
      });
      pick.show();
    });
  };

  const rowHtml = (r, kind) => `
    <div class="rm-door-row" data-booking="${esc(r.name)}">
      <div class="rm-door-who">
        <strong>${esc(r.guest)}</strong>
        <span class="rm-door-meta">${esc(r.covers)} ${r.covers === 1 ? __("cover") : __("covers")}${
          r.contact ? " · " + esc(r.contact) : ""}${
          kind === "waiting" ? " · " + __("waiting {0} min", [r.waited])
                             : " · " + esc((r.at || "").slice(11, 16)) + (r.table_label ? " · " + esc(r.table_label) : "")}</span>
      </div>
      <div class="rm-door-actions">
        <button class="btn btn-xs btn-primary rm-seat">${__("Seat")}</button>
        <button class="btn btn-xs btn-default rm-noshow">${__("No show")}</button>
      </div>
    </div>`;

  const render = (dialog, data) => {
    const { summary, waiting, expected } = data;
    const wrap = dialog.fields_dict.board.$wrapper;
    wrap.html(`
      <div class="rm-door">
        <div class="rm-door-summary">
          <span><strong>${summary.waiting}</strong> ${__("waiting")}</span>
          <span><strong>${summary.covers_waiting}</strong> ${__("covers")}</span>
          <span><strong>${summary.longest_wait}</strong> ${__("min longest")}</span>
          <span><strong>${summary.free_tables}</strong> ${__("tables free")}</span>
          <span><strong>${summary.seated_now}</strong> ${__("seated")}</span>
          <span title="${__("Average time a party sat today")}"><strong>${summary.avg_turn || "—"}</strong> ${__("min avg turn")}</span>
        </div>
        <h5 class="rm-door-head">${__("At the door")}</h5>
        ${waiting.length ? waiting.map(r => rowHtml(r, "waiting")).join("")
                         : `<p class="text-muted small">${__("Nobody waiting.")}</p>`}
        <h5 class="rm-door-head">${__("Expected today")}</h5>
        ${expected.length ? expected.map(r => rowHtml(r, "expected")).join("")
                          : `<p class="text-muted small">${__("No bookings today.")}</p>`}
      </div>`);

    const find = (el) => {
      const name = $(el).closest(".rm-door-row").data("booking");
      return waiting.concat(expected).find(r => r.name === name);
    };
    wrap.find(".rm-seat").on("click", function () { seatParty(find(this), dialog); });
    wrap.find(".rm-noshow").on("click", function () {
      const row = find(this);
      frappe.confirm(__("Mark {0} as a no-show?", [row.guest]), () => {
        call("close_booking", { booking: row.name, status: "No Show" }).then(() => refresh(dialog));
      });
    });
  };

  const refresh = (dialog) => Promise.all([call("door_summary"), call("waitlist"), call("reservations")])
    .then(([summary, waiting, expected]) => render(dialog, { summary, waiting, expected }));

  window.RM_door = {
    mounted: false,

    mount(rm) {
      if (this.mounted || !rm.page || !rm.page.add_inner_button) return;
      this.mounted = true;
      rm.page.add_inner_button(__("Door"), () => RM_door.open());
      this.badge();
    },

    badge() {
      call("door_summary").then(s => {
        if (!s) return;
        const btn = $(".page-actions button").filter((i, b) => /Door/.test($(b).text())).first();
        if (btn.length) btn.text(s.waiting ? __("Door ({0})", [s.waiting]) : __("Door"));
      });
    },

    open() {
      const dialog = new frappe.ui.Dialog({
        title: __("Door"),
        size: "large",
        fields: [
          { fieldname: "guest_name", fieldtype: "Data", label: __("Add to the queue") },
          { fieldname: "covers", fieldtype: "Int", label: __("Guests"), default: 2 },
          { fieldname: "contact", fieldtype: "Data", label: __("Phone (optional)") },
          { fieldname: "board", fieldtype: "HTML" },
        ],
        primary_action_label: __("Add to queue"),
        primary_action: ({ guest_name, covers, contact }) => {
          if (!guest_name) return;
          call("add_to_waitlist", { guest_name, covers: covers || 2, contact }).then(() => {
            dialog.set_value("guest_name", "");
            dialog.set_value("contact", "");
            refresh(dialog).then(() => RM_door.badge());
          });
        },
      });
      dialog.show();
      refresh(dialog);
    },
  };
})();
