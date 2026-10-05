// rm_till_withdrawal: paste the Safaricom SMS and the form fills itself in.
frappe.ui.form.on("Till Withdrawal", {
	sms_text(frm) {
		if (!frm.doc.sms_text || frm.doc.docstatus !== 0) return;
		frappe.call({
			method: "restaurant_management.restaurant_management.doctype.till_withdrawal.till_withdrawal.preview",
			args: { sms_text: frm.doc.sms_text },
		}).then(({ message: p }) => {
			if (!p) return;
			["reference", "amount", "withdrawn_at", "transaction_cost", "balance_after"].forEach((f) => {
				if (p[f] !== null && p[f] !== undefined && p[f] !== "") frm.set_value(f, p[f]);
			});
			(p.warnings || []).forEach((w) => frappe.show_alert({ message: w, indicator: "orange" }, 8));
		});
	},
	refresh(frm) {
		if (frm.doc.journal_entry) {
			frm.add_custom_button(__("Journal Entry"), () => frappe.set_route("Form", "Journal Entry", frm.doc.journal_entry));
		}
	},
});
