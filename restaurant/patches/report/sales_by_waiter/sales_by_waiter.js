frappe.query_reports["Sales by Waiter"] = {
  filters: [
    {
      fieldname: "from_date", label: __("From Date"), fieldtype: "Date",
      default: frappe.datetime.add_days(frappe.datetime.get_today(), -7), reqd: 1,
    },
    {
      fieldname: "to_date", label: __("To Date"), fieldtype: "Date",
      default: frappe.datetime.get_today(), reqd: 1,
    },
    { fieldname: "pos_profile", label: __("POS Profile"), fieldtype: "Link", options: "POS Profile" },
  ],
};
