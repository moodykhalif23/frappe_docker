
// Seats, not tables. A six-top with two guests on it has four seats to sell,
// and each party on it keeps its own waiter.
(() => {
  if (window.RM_seats) return;

  const call = (m, args) => frappe.call("restaurant_management.house." + m, args || {}).then(r => r.message);

  const party_badge = (p) => {
    // A check with nobody seated through the door is a thing, not a person.
    if (p.unseated) {
      return `<span class="rm-party" style="background-color:#4b5563" title="${
        frappe.utils.escape_html(__("An unpaid order is open on this table"))}"><span class="fa fa-cutlery"></span>&nbsp;${__("open check")}</span>`;
    }
    const who = p.initials || "";
    const title = `${p.guest} · ${p.covers || "?"} ${__("covers")}${p.waiter ? " · " + p.waiter : ""}`;
    return `<span class="rm-party" style="background-color:${p.colour}" title="${frappe.utils.escape_html(title)}">${
      frappe.utils.escape_html(who)}<i>${p.covers || "?"}</i></span>`;
  };

  const CAPS = (frappe.boot && frappe.boot.user && frappe.boot.user.can_create) || [];
  const CAN_BANK = CAPS.indexOf("POS Closing Entry") !== -1;
  const CAN_BILL = CAPS.indexOf("POS Invoice") !== -1;
  const ROLES = frappe.user_roles || [];
  // Administrator holds every role, so a station role alone would strip its own
  // floor bare. A real station is one that cannot bank the day.
  const IS_STATION = !CAN_BANK && frappe.session.user !== "Administrator";
  const IS_KITCHEN_STATION = IS_STATION && ROLES.indexOf("Kitchen Station") !== -1;
  const IS_WAITER_STATION = IS_STATION && ROLES.indexOf("Waiter Station") !== -1;

  window.RM_seats = {
    map: {},
    mounted: false,
    timer: null,

    mount(rm) {
      if (this.mounted) return;
      this.mounted = true;
      // Release is rare and cashier-only, so it lives in the page menu: a sixth
      // toolbar button pushes every one-tap control into an overflow dropdown.
      if (rm && rm.page && rm.page.add_menu_item && CAN_BANK) {
        rm.page.add_menu_item(__("Release a table"), () => RM_seats.release_dialog());
      }
      document.body.classList.toggle("rm-station-kitchen", IS_KITCHEN_STATION);
      document.body.classList.toggle("rm-station-waiter", IS_WAITER_STATION);
      // Editing the floor plan is a manager's job: without the permission the
      // server refuses anyway, so do not offer the pencil at all.
      const CAN_EDIT_FLOOR = (CAPS.indexOf("Restaurant Object") !== -1);
      document.body.classList.toggle("rm-no-floor-edit", !CAN_EDIT_FLOOR);
      if (IS_KITCHEN_STATION) {
        const hideFront = () => $(".page-actions button").filter(function () {
          return /Seat guest|Waiter|Door|Release|Open day|Close day/.test($(this).text().trim());
        }).hide();
        setTimeout(hideFront, 1500);
        setTimeout(hideFront, 5000);
      }
      if (!CAN_BILL) {
        // the money button never shows on a station that cannot take money
        setInterval(() => $(".order-manage button, .order-manage .pad-btn").filter(function () {
          return /^\s*Complete\s*$/.test($(this).text());
        }).hide(), 2000);
      }
      // The floor is still wiring itself up; do not compete with it.
      setTimeout(() => RM_seats.refresh(), 1500);
      // Polling every ten seconds showed up as a slow floor; realtime carries it.
      this.timer = setInterval(() => RM_seats.refresh(), 60000);
      // Checks moving usually means seats moved with them.
      frappe.realtime.on("synchronize_order_data", () => RM_seats.soon());

      this.watch_floor();
    },

    soon() {
      clearTimeout(this.pending);
      this.pending = setTimeout(() => RM_seats.refresh(), 800);
    },

    seats(table) {
      return this.map[table] || null;
    },

    refresh() {
      return Promise.all([call("table_occupancy"), call("floor_waiters")]).then(([m, w]) => {
        RM_seats.map = m || {};
        RM_seats.holders = w || {};
        RM_seats.paint();
        return RM_seats.map;
      });
    },

    watch_floor() {
      if (this.observer || typeof MutationObserver === "undefined") return;
      const target = document.querySelector(".restaurant-manage") || document.body;
      this.observer = new MutationObserver(() => {
        if (RM_seats.painting) return;
        clearTimeout(RM_seats.repaint_timer);
        RM_seats.repaint_timer = setTimeout(() => RM_seats.paint(), 400);
      });
      this.observer.observe(target, { childList: true, subtree: true });
    },

    paint() {
      // our own writes are mutations too — do not chase them
      this.painting = true;
      try {
        Object.keys(this.map).forEach((name) => RM_seats.paint_table(name));
      } finally {
        setTimeout(() => { RM_seats.painting = false; }, 150);
      }
    },

    paint_table(name) {
      const seats = this.map[name];
      if (!seats) return;

      // Find the tile in the live document: a room re-render replaces the nodes
      // the cached RestaurantObject still points at, so its JSHtml writes vanish.
      let el = null;
      $(".floor-map .d-table").each(function () {
        const label = $(this).find(".d-label").first().text().trim();
        if (label === seats.description || label === name) el = $(this);
      });
      if (!el || !el.length) {
        const obj = window.RM && RM.object && RM.object(name);
        if (!obj || !obj.obj || !obj.obj.obj) return;
        el = $(obj.obj.obj);
      }

      const pill = el.find(".d-table-seats").first();
      if (pill.length && seats.capacity) {
        const text = seats.occupied ? `${seats.occupied}/${seats.capacity}` : String(seats.capacity);

        if (pill.text().trim() !== text) {
          const icon = pill.find(".fa").first();
          pill.text(" " + text);
          if (icon.length) pill.prepend(icon);
        }
      }
      el.toggleClass("rm-full", seats.free === 0 && !!seats.capacity);
      el.toggleClass("rm-shared", seats.parties.length > 1);

      const box = el.find(".resize-handle-container").first();
      if (!box.length) return;

      const wanted = seats.parties.length
        ? `<span class="rm-party-badges">${seats.parties.map(party_badge).join("")}</span>` : "";
      const existing = box.find(".rm-party-badges");
      const unchanged = wanted
        ? (existing.length === 1 && existing[0].outerHTML === wanted)
        : existing.length === 0;
      if (unchanged) {
        el.find(".d-waiter-badge").toggle(!seats.parties.length);
        return;
      }
      existing.remove();

      // The section badge lives on live data, not the tile's first render — a
      // released table must lose its initials without waiting for a reload.
      const holder = (this.holders || {})[name];
      let badge = el.find(".d-waiter-badge");
      if (!seats.parties.length && holder) {
        if (!badge.length) {
          box.append(`<span class="d-waiter-badge"></span>`);
          badge = el.find(".d-waiter-badge");
        }
        badge.attr("data-waiter", holder.waiter).attr("title", holder.waiter)
          .css("background-color", holder.colour || "#4b5563")
          .text(holder.initials || "").show();
      } else {
        badge.remove();
      }

      if (!seats.parties.length) return;
      box.append(wanted);
    },

    release_dialog() {
      this.refresh().then((map) => {
        const holders = RM_seats.holders || {};
        const held = Object.values(map || {}).filter(s => s.parties.length);
        // A waiter can hold a section on an empty table; that hold releases too.
        const seated = new Set(held.map(s => s.table));
        Object.entries(holders || {}).forEach(([table, w]) => {
          if (!seated.has(table)) held.push({ table,
            description: (map[table] || {}).description || table,
            parties: [], section: w.waiter });
        });
        if (!held.length) {
          frappe.msgprint({ title: __("Nothing to release"), indicator: "blue",
            message: __("No table is holding a party, an open check or a section.") });
          return;
        }
        const label = (s) => s.section
          ? `${s.description} — ${__("section")}: ${s.section}`
          : `${s.description} — ${s.parties.map(p =>
              p.unseated ? __("open check") : `${p.guest} · ${p.covers}`).join(", ")}`;
        const d = new frappe.ui.Dialog({
          title: __("Release a table"),
          fields: [
            { fieldname: "table", fieldtype: "Select", label: __("Table"), reqd: 1,
              options: held.map(s => ({ value: s.table, label: label(s) })) },
            { fieldtype: "HTML", options: `<p class="text-muted small">${
              __("Cancels the table's unpaid checks and closes its seatings. Paid sales are never touched.")}</p>` },
          ],
          primary_action_label: __("Release"),
          primary_action: ({ table }) => {
            d.hide();
            call("release_table", { table }).then((r) => {
              frappe.show_alert({ message: __("{0} released — {1} check(s), {2} seating(s) closed",
                [table, (r && r.orders || []).length, (r && r.bookings || []).length]), indicator: "green" });
              RM_seats.refresh();
            });
          },
          secondary_action_label: __("Keep it"),
          secondary_action: () => d.hide(),
        });
        d.show();
      });
    },

    pick_check(om, done) {
      const orders = om.child_values || [];
      if (!orders.length) return false;
      // one question at a time, however many code paths ask it
      if (om.__picking) return true;
      om.__picking = true;
      setTimeout(() => { om.__picking = false; }, 15000);
      if (orders.length === 1) {
        om.__picking = false;
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
            om.__picking = false;
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
