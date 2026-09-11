frappe.query_reports["Waiter Day Book"] = {
  filters: [
    {
      fieldname: "waiter", label: __("Waiter"), fieldtype: "Link", options: "Restaurant Waiter",
      // blank shows the whole floor; pick one to answer for a single server
    },
    {
      fieldname: "from_date", label: __("From Date"), fieldtype: "Date",
      default: frappe.datetime.get_today(), reqd: 1,
    },
    {
      fieldname: "to_date", label: __("To Date"), fieldtype: "Date",
      default: frappe.datetime.get_today(), reqd: 1,
    },
    {
      // "Per item" is what was sold; "Per check" is what was banked
      fieldname: "view", label: __("Show"), fieldtype: "Select",
      options: ["Per item", "Per check"], default: "Per item",
    },
    {
      fieldname: "include", label: __("Include"), fieldtype: "Select",
      options: ["Billed only", "Billed and open"], default: "Billed only",
    },
    { fieldname: "pos_profile", label: __("POS Profile"), fieldtype: "Link", options: "POS Profile" },
    {
      fieldname: "room", label: __("Room"), fieldtype: "Link", options: "Restaurant Object",
      get_query: () => ({ filters: { type: "Room" } }),
    },
  ],

  formatter(value, row, column, data, default_formatter) {
    const out = default_formatter(value, row, column, data);
    // an open check has no bill behind it yet: say so rather than showing a blank
    if (column.fieldname === "status" && value && /^(Cancelled|Voided)$/i.test(value)) {
      return `<span style="color:var(--red-500)">${frappe.utils.escape_html(value)}</span>`;
    }
    return out;
  },
};
