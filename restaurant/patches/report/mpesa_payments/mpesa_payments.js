// Every M-Pesa shilling with the code the customer read off their phone, so
// the day's mobile money reconciles against the statement line by line.
frappe.query_reports["M-Pesa Payments"] = {
  filters: [
    { fieldname: "from_date", label: __("From"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
    { fieldname: "to_date", label: __("To"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
    { fieldname: "code", label: __("Code"), fieldtype: "Data", description: __("Find one confirmation code") },
    { fieldname: "waiter", label: __("Waiter"), fieldtype: "Link", options: "Restaurant Waiter" },
  ],
};
