
// rm_reprint: a bill that failed to print is otherwise unreachable — an
// invoiced check sets show_in_pos = 0 and drops off the pad. Lists recent
// checks and prints the right document: the receipt once paid, the order bill
// while still open.
//
// The HTML goes in as the field's `options` — setting it on the wrapper before
// show() is wiped when frappe re-renders its fields, which left an empty box.
(() => {
  if (window.RM_reprint && window.RM_reprint.__v3) return;

  const esc = (s) => frappe.utils.escape_html(String(s == null ? "" : s));

  const row_html = (r, i) => `
    <div style="display:flex;justify-content:space-between;align-items:center;
                padding:8px 2px;border-bottom:1px solid var(--border-color,#e5e5e5)">
      <div style="min-width:0">
        <b>${esc(r.table) || esc(r.order)}</b>${r.guest ? " &middot; " + esc(r.guest) : ""}
        <div class="text-muted" style="font-size:11px">
          ${esc(r.invoice || r.order)} &middot; ${esc(r.time)} &middot; ${r.invoice ? __("receipt") : __("open check")}
        </div>
      </div>
      <div style="text-align:right;white-space:nowrap;padding-left:10px">
        <b>${esc(r.amount)}</b>
        <button class="btn btn-xs btn-primary rm-rp-btn" style="margin-left:8px" data-i="${i}">${__("Print")}</button>
      </div>
    </div>`;

  window.RM_reprint = {
    __v3: true,
    open() {
      frappe.call("restaurant_management.house.recent_bills", { limit: 25 })
        .then(({ message }) => {
          const rows = message || [];
          if (!rows.length) return frappe.msgprint(__("No recent bills to reprint"));
          const html = '<div class="rm-rp-list">' + rows.map(row_html).join("") + "</div>";

          const dialog = new frappe.ui.Dialog({
            title: __("Reprint a bill"),
            fields: [{ fieldname: "rm_rp_list", fieldtype: "HTML", options: html }],
          });

          dialog.$wrapper.on("click", ".rm-rp-btn", (e) => {
            const r = rows[parseInt(e.currentTarget.getAttribute("data-i"), 10)];
            if (!r) return;
            try {
              if (r.invoice) { RM_print_receipt(r.invoice); } else { RM_print_ticket(r.order); }
              dialog.hide();
            } catch (err) {
              console.error("RM_reprint print", err);
              frappe.msgprint({ title: __("Print failed"), indicator: "red",
                message: String((err && err.message) || err) });
            }
          });

          dialog.show();
          // belt and braces: if frappe rendered the field empty, fill it now
          setTimeout(() => {
            try {
              const $b = dialog.$wrapper.find(".rm-rp-list");
              if (!$b.length) {
                const f = dialog.fields_dict.rm_rp_list;
                (f && f.$wrapper ? f.$wrapper : dialog.$wrapper.find(".modal-body")).html(html);
              }
            } catch (e) { console.error("RM_reprint fill", e); }
          }, 0);
        })
        .catch((e) => {
          console.error("RM_reprint call", e);
          frappe.msgprint({ title: __("Reprint failed"), indicator: "red",
            message: String((e && (e.message || e.responseText)) || e) });
        });
    },
  };
})();
