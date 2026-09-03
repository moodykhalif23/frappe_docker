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
    {
      // riders live in the Delivery room: filter to it for their commission base
      fieldname: "room", label: __("Room"), fieldtype: "Link", options: "Restaurant Object",
      get_query: () => ({ filters: { type: "Room" } }),
    },
    {
      // the seater owns the check; whoever tapped Order owns each line
      fieldname: "credit", label: __("Credit"), fieldtype: "Select",
      options: ["Check owner", "Lines fired"], default: "Check owner",
    },
  ],
};
