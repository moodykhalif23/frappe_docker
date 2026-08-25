frappe.query_reports["Restock List"] = {
  filters: [
    { fieldname: "warehouse", label: __("Store"), fieldtype: "Link", options: "Warehouse" },
    { fieldname: "show_all", label: __("Show everything, not just what is short"), fieldtype: "Check" },
  ],
};
