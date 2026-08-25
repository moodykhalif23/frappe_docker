frappe.query_reports["Restock List"] = {
  filters: [
    { fieldname: "warehouse", label: __("Warehouse"), fieldtype: "Link", options: "Warehouse" },
    { fieldname: "only_short", label: __("Only what needs restocking"), fieldtype: "Check", default: 1 },
  ],
  formatter(value, row, column, data, def) {
    const out = frappe.query_reports.default_formatter(value, row, column, data, def)
    if (data && data.needs_restock && column.fieldname === "item_name") {
      return `<span style="color:var(--red-600,#b91c1c);font-weight:600">${out}</span>`
    }
    return out
  },
}
