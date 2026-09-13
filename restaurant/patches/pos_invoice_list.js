// rm_reprint_list: a Reprint button on every row of the POS Invoice list, so a
// bill that failed to print can be run again from the place staff already go to
// find it — with the list's own search and date filters, not just a recent-25.
//
// Self-contained on purpose: pay-form-class.js (which owns RM_print_receipt)
// is only loaded by the restaurant-manage page, not across the desk.
frappe.provide("frappe.listview_settings");

window.rm_reprint_invoice = function (name, fmt) {
	if (!name) return;
	const params = new URLSearchParams({
		doctype: "POS Invoice",
		name: name,
		format: fmt || "Etham Receipt",
		no_letterhead: 1,
		trigger_print: 1,
	});
	const old = document.getElementById("rm-reprint-frame");
	if (old && old.parentNode) old.parentNode.removeChild(old);
	const f = document.createElement("iframe");
	f.id = "rm-reprint-frame";
	f.style.cssText = "position:fixed;left:-9999px;top:0;width:0;height:0;border:0";
	f.src = "/printview?" + params.toString();
	document.body.appendChild(f);
	frappe.show_alert({ message: __("Reprinting {0}", [name]), indicator: "blue" });
	// the frame's own trigger_print fires window.print(); clean it up after
	setTimeout(function () {
		try { if (f.parentNode) f.parentNode.removeChild(f); } catch (e) { /* gone already */ }
	}, 30000);
};

frappe.listview_settings["POS Invoice"] = Object.assign(
	{},
	frappe.listview_settings["POS Invoice"] || {},
	{
		button: {
			show: function (doc) { return !!doc.name; },
			get_label: function () { return __("Reprint"); },
			get_description: function (doc) { return __("Reprint the receipt for {0}", [doc.name]); },
			action: function (doc) { window.rm_reprint_invoice(doc.name); },
		},
	}
);
