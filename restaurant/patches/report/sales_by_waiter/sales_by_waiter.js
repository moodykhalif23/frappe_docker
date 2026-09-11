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

  formatter(value, row, column, data, default_formatter) {
    // the waiter's name opens their day book on the same dates and the same basis
    if (column.fieldname === "waiter" && data && data.waiter && data.waiter !== "Unassigned") {
      const f = frappe.query_report.get_filter_values() || {};
      const q = {
        waiter: data.waiter,
        from_date: f.from_date || frappe.datetime.get_today(),
        to_date: f.to_date || frappe.datetime.get_today(),
        view: f.credit === "Lines fired" ? "Per item" : "Per check",
      };
      if (f.pos_profile) q.pos_profile = f.pos_profile;
      if (f.room) q.room = f.room;
      const href = `/app/query-report/${encodeURIComponent("Waiter Day Book")}?${frappe.utils.get_url_from_dict(q)}`;
      return `<a href="${href}" title="${__("Open this waiter's day book")}"
              >${frappe.utils.escape_html(data.waiter)}</a>`;
    }
    return default_formatter(value, row, column, data);
  },
};
