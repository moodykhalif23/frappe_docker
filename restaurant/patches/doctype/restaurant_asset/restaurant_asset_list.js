frappe.listview_settings["Restaurant Asset"] = {
  add_fields: ["status", "quantity"],
  get_indicator(doc) {
    const map = { "In Use": "green", "In Store": "blue", "Damaged": "orange", "Written Off": "red" };
    return [__(doc.status || "In Use"), map[doc.status] || "grey", "status,=," + (doc.status || "In Use")];
  },

  onload(list) {
    list.page.add_inner_button(__("Add several"), () => open_bulk(), null, "primary");
  },
};

// One category, many things: chairs into Furniture, spoons into Utensils, without
// closing the dialog between each. The list refreshes as they land.
function open_bulk(category) {
  const rows = [];
  const d = new frappe.ui.Dialog({
    title: __("Add assets"),
    fields: [
      {
        fieldname: "asset_category", fieldtype: "Link", options: "Restaurant Asset Category",
        label: __("Category"), reqd: 1, default: category || "",
        description: __("Set it once — everything you add below goes here until you change it."),
      },
      { fieldname: "asset_name", fieldtype: "Data", label: __("What is it"), reqd: 1 },
      { fieldname: "quantity", fieldtype: "Int", label: __("How many"), default: 1 },
      { fieldname: "location", fieldtype: "Data", label: __("Where it is") },
      { fieldname: "added", fieldtype: "HTML" },
    ],
    primary_action_label: __("Add and keep going"),
    primary_action: (v) => save_one(d, v, rows, false),
    secondary_action_label: __("Add and close"),
    secondary_action: () => save_one(d, d.get_values(true), rows, true),
  });
  d.show();
  setTimeout(() => d.get_field("asset_name").$input && d.get_field("asset_name").$input.focus(), 300);
}

function save_one(d, v, rows, close) {
  if (!v || !v.asset_category || !v.asset_name) {
    frappe.show_alert({ message: __("A category and a name, then it is in."), indicator: "orange" });
    return;
  }
  frappe.call({
    method: "frappe.client.insert",
    args: {
      doc: {
        doctype: "Restaurant Asset", asset_name: v.asset_name, asset_category: v.asset_category,
        quantity: v.quantity || 1, location: v.location || "", status: "In Use",
      },
    },
  }).then(({ message }) => {
    if (!message) return;
    rows.unshift(`${frappe.utils.escape_html(v.asset_name)} · ${v.quantity || 1} · ${
      frappe.utils.escape_html(v.asset_category)}`);
    d.get_field("added").$wrapper.html(
      `<div class="text-muted small" style="margin-top:6px">${__("Added this session")}:<br>${
        rows.slice(0, 8).map(r => "• " + r).join("<br>")}${
        rows.length > 8 ? `<br>${__("and {0} more", [rows.length - 8])}` : ""}</div>`);
    // the name clears, the category stays: the next thing is usually in the same one
    d.set_value("asset_name", "");
    d.set_value("quantity", 1);
    frappe.show_alert({ message: __("{0} added", [message.name]), indicator: "green" });
    if (cur_list && cur_list.doctype === "Restaurant Asset") cur_list.refresh();
    if (close) return d.hide();
    setTimeout(() => d.get_field("asset_name").$input && d.get_field("asset_name").$input.focus(), 150);
  });
}
