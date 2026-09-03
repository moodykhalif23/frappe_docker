# The pad showed the receipt in a modal that embeds a PDF, and the embed never
# laid out — the dialog opened with a title and nothing under it.
P = "apps/restaurant_management/restaurant_management/public/restaurant/js/pay-form-class.js"

src = open(P).read()

# an earlier bake opened a second tab and waited for a click on Print
if "RM_print_url(" not in src and "window.open(\"/printview?\"" in src:
    src = src.replace('  const win = window.open("/printview?" + params.toString(), "_blank");',
                      '  RM_print_url("/printview?" + params.toString());', 1)
    import re as _re
    src = _re.sub(r'\n  if \(!win\) \{\n    frappe\.msgprint\(\{[^}]*\}\);\n  \}\n', '\n', src, count=1)
    open(P if "P" in dir() else PAY, "w").write(src)
    print("RM_print_receipt: prints from a hidden frame, no second tab")
if "RM_print_receipt" in src and "window.RM_print_url" not in src:
    open(P, "w").write(src + """
// Print a frappe print view from THIS tab: a hidden frame loads it, the page's
// trigger_print calls window.print() the moment it renders, and the frame goes
// away after printing. Under Chrome's --kiosk-printing the dialog auto-confirms.
window.RM_print_url = window.RM_print_url || function (url) {
  const old = document.getElementById("rm-print-frame");
  if (old) old.remove();
  const f = document.createElement("iframe");
  f.id = "rm-print-frame";
  f.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden";
  f.src = url;
  document.body.appendChild(f);
  const done = () => setTimeout(() => f.remove(), 1000);
  f.addEventListener("load", () => {
    try { f.contentWindow.addEventListener("afterprint", done); } catch (e) { /* cross-origin never happens here */ }
    setTimeout(done, 90000);
  });
};
""")
    src = open(P).read()
    print("receipt: hidden-frame printer added")
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
// Print a frappe print view from THIS tab: a hidden frame loads it, the page's
// trigger_print calls window.print() the moment it renders, and the frame goes
// away after printing. Under Chrome's --kiosk-printing the dialog auto-confirms.
window.RM_print_url = window.RM_print_url || function (url) {
  const old = document.getElementById("rm-print-frame");
  if (old) old.remove();
  const f = document.createElement("iframe");
  f.id = "rm-print-frame";
  f.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden";
  f.src = url;
  document.body.appendChild(f);
  const done = () => setTimeout(() => f.remove(), 1000);
  f.addEventListener("load", () => {
    try { f.contentWindow.addEventListener("afterprint", done); } catch (e) { /* cross-origin never happens here */ }
    setTimeout(done, 90000);
  });
};

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

  RM_print_url("/printview?" + params.toString());
};
'''

open(P, "w").write(src.replace(OLD, NEW, 1) + HELPER)
print("receipt: prints through the frappe print view")
