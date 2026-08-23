
// Waiter pad. Waiters have no logins: they tap a name and PIN on the shared
// terminal, then own the tables they claim until someone else takes them.
(() => {
  if (window.RM_waiter) return;

  const STORE = "rm_waiter_session";
  let colours = {};

  const initials = (name) => {
    const parts = (name || "").split(/\s+/).filter(Boolean);
    if (!parts.length) return "";
    return (parts.length > 1 ? parts[0][0] + parts[parts.length - 1][0] : parts[0].slice(0, 2)).toUpperCase();
  };

  const session = () => {
    try { return JSON.parse(localStorage.getItem(STORE) || "null"); } catch (e) { return null; }
  };
  const remember = (s) => {
    try { localStorage.setItem(STORE, JSON.stringify(s)); } catch (e) { /* private mode */ }
  };

  // Badge printed on every table tile, so a glance says whose section is buried.
  window.RM_waiter_badge = (waiter) => {
    if (!waiter) return "";
    const colour = colours[waiter] || "#4b5563";
    return `<span class="d-waiter-badge" data-waiter="${frappe.utils.escape_html(waiter)}"
      title="${frappe.utils.escape_html(waiter)}" style="background-color:${colour}">${initials(waiter)}</span>`;
  };

  const paint = () => {
    $(".d-waiter-badge").each(function () {
      const w = $(this).attr("data-waiter");
      if (colours[w]) $(this).css("background-color", colours[w]);
    });
  };

  const load_colours = () => frappe.call("restaurant_management.house.floor_waiters").then(({ message }) => {
    Object.values(message || {}).forEach(v => { if (v.waiter) colours[v.waiter] = v.colour; });
    paint();
  });

  const assign_tables = (who) => {
    frappe.call("restaurant_management.house.free_tables", {}).then(() => {
      frappe.call("restaurant_management.house.floor_waiters").then(({ message }) => {
        const held = message || {};
        frappe.call("frappe.client.get_list", {
          doctype: "Restaurant Object", filters: { type: "Table" },
          fields: ["name", "description"], limit_page_length: 0,
        }).then(({ message: tables }) => {
          const dialog = new frappe.ui.Dialog({
            title: __("Give tables to {0}", [who.waiter_name]),
            fields: [{
              fieldname: "tables", fieldtype: "MultiCheck", label: __("Tables"), columns: 2,
              options: (tables || []).map(t => ({
                label: held[t.name] && held[t.name].waiter
                  ? `${t.description || t.name} — ${held[t.name].waiter}`
                  : (t.description || t.name),
                value: t.name,
              })),
            }],
            primary_action_label: __("Assign"),
            primary_action: ({ tables: picked }) => {
              const chosen = picked || [];
              if (!chosen.length) return dialog.hide();
              Promise.all(chosen.map(t => frappe.call("restaurant_management.house.claim_table", {
                table: t, waiter: who.waiter, token: who.token,
              }))).then(() => {
                dialog.hide();
                frappe.show_alert({ message: __("{0} now has {1} table(s)", [who.waiter_name, chosen.length]), indicator: "green" });
                load_colours().then(() => RM.reload_rooms && RM.reload_rooms());
              });
            },
          });
          dialog.show();
        });
      });
    });
  };

  window.RM_waiter = {
    mounted: false,
    get current() { return session(); },

    mount(rm) {
      if (this.mounted || !rm.page || !rm.page.add_inner_button) return;
      this.mounted = true;
      const who = session();
      rm.page.add_inner_button(who ? __("Waiter: {0}", [who.initials]) : __("Waiter"), () => RM_waiter.open());
      load_colours();
    },

    open() {
      const who = session();
      if (who) return this.signed_in(who);
      frappe.call("restaurant_management.house.waiters").then(({ message }) => {
        const list = message || [];
        if (!list.length) {
          frappe.msgprint({
            title: __("No waiters yet"),
            message: __("Add them under Restaurant Waiter — a name and a 4-digit PIN each."),
            indicator: "orange",
          });
          return;
        }
        const dialog = new frappe.ui.Dialog({
          title: __("Who's on?"),
          fields: [
            {
              fieldname: "waiter", fieldtype: "Select", label: __("Waiter"), reqd: 1,
              options: list.map(w => ({ value: w.name, label: w.waiter_name })),
            },
            { fieldname: "pin", fieldtype: "Password", label: __("PIN"), reqd: 1 },
          ],
          primary_action_label: __("Sign in"),
          primary_action: ({ waiter, pin }) => {
            frappe.call({
              method: "restaurant_management.house.waiter_sign_in",
              args: { waiter, pin },
              freeze: true,
            }).then(({ message: signed }) => {
              if (!signed) return;
              remember(signed);
              dialog.hide();
              frappe.show_alert({ message: __("Signed in as {0}", [signed.waiter_name]), indicator: "green" });
              RM_waiter.signed_in(signed);
            });
          },
        });
        dialog.show();
      });
    },

    signed_in(who) {
      const dialog = new frappe.ui.Dialog({
        title: __("{0} is on", [who.waiter_name]),
        fields: [{
          fieldname: "info", fieldtype: "HTML",
          options: `<p class="text-muted">${__("Tables you claim are yours until someone else takes them.")}</p>`,
        }],
        primary_action_label: __("Take tables"),
        primary_action: () => { dialog.hide(); assign_tables(who); },
        secondary_action_label: __("Sign out"),
        secondary_action: () => {
          try { localStorage.removeItem(STORE); } catch (e) { /* ignore */ }
          dialog.hide();
          frappe.show_alert({ message: __("Signed out"), indicator: "blue" });
        },
      });
      dialog.show();
    },
  };
})();
