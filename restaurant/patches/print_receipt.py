# The pad showed the receipt in a modal that embeds a PDF, and the embed never
# laid out — the dialog opened with a title and nothing under it.
P = "apps/restaurant_management/restaurant_management/public/restaurant/js/pay-form-class.js"

src = open(P).read()
if "RM_print_receipt" in src:
    print("receipt: already opens the print view")
    raise SystemExit

OLD = '''  print(invoice_name) {
    if (!RM.can_pay) return;

    const title = invoice_name + " (" + __("Print") + ")";
    const order_manage = this.order.order_manage;

    const props = {
      model: "POS Invoice",
      model_name: invoice_name,
      args: {
        format: RM.pos_profile.print_format || "POS Invoice",
        _lang: RM.lang,
        no_letterhead: RM.pos_profile.letter_head || 1,
        letterhead: RM.pos_profile.letter_head || 'No%20Letterhead'
      },
      from_server: true,
      set_buttons: true,
      is_pdf: true,
      customize: true,
      title: title
    };

    if (order_manage.print_modal) {
      order_manage.print_modal.set_props(props);
      order_manage.print_modal.set_title(title);
      order_manage.print_modal.reload().show();
    } else {
      order_manage.print_modal = new DeskModal(props);
    }
  }'''

NEW = '''  print(invoice_name) {
    if (!RM.can_pay) return;
    RM_print_receipt(invoice_name);
  }'''

if OLD not in src:
    raise SystemExit("receipt: print() anchor not found in pay-form-class.js")

HELPER = '''
// The receipt opens as frappe's own print view, which renders and offers the
// browser's print dialog — the PDF embed it replaced showed a blank modal.
window.RM_print_receipt = function (invoice_name) {
  const profile = (window.RM && RM.pos_profile) || {};
  const params = new URLSearchParams({
    doctype: "POS Invoice",
    name: invoice_name,
    format: profile.print_format || "POS Invoice",
    no_letterhead: profile.letter_head ? 0 : 1,
    trigger_print: 1,
  });
  if (profile.letter_head) params.set("letterhead", profile.letter_head);
  if (window.RM && RM.lang) params.set("_lang", RM.lang);

  const win = window.open("/printview?" + params.toString(), "_blank");
  if (!win) {
    frappe.msgprint({
      title: __("Allow pop-ups to print"),
      indicator: "orange",
      message: __("The receipt opens in a new tab. This browser blocked it — allow pop-ups for this site."),
    });
  }
};
'''

open(P, "w").write(src.replace(OLD, NEW, 1) + HELPER)
print("receipt: prints through the frappe print view")
