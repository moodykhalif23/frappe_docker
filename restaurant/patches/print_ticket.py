# The kitchen ticket and the pre-payment bill used the same PDF-embed modal the
# receipt did — a dialog that opens with a title and nothing under it.
PAY = "apps/restaurant_management/restaurant_management/public/restaurant/js/pay-form-class.js"
PROCESS = "apps/restaurant_management/restaurant_management/public/restaurant/js/process-manage-class.js"
ORDER = "apps/restaurant_management/restaurant_management/public/restaurant/js/table-order-class.js"

src = open(PAY).read()
if "RM_print_ticket" in src:
    print("ticket print: already applied")
    raise SystemExit

HELPER = '''
// A kitchen ticket or a table bill opens as frappe's print view of the order.
window.RM_print_ticket = function (order_name) {
  const params = new URLSearchParams({
    doctype: "Table Order",
    name: order_name,
    format: "Order Account",
    no_letterhead: 1,
    trigger_print: 1,
  });
  if (window.RM && RM.lang) params.set("_lang", RM.lang);
  const win = window.open("/printview?" + params.toString(), "_blank");
  if (!win) {
    frappe.msgprint({
      title: __("Allow pop-ups to print"),
      indicator: "orange",
      message: __("The ticket opens in a new tab. This browser blocked it — allow pop-ups for this site."),
    });
  }
};
'''
open(PAY, "w").write(src + HELPER)

# An ungrouped board knows only the item; the server names the order behind it.
psrc = open(PROCESS).read()
OLD_P = '''  print_order(data) {
    const title = data.name + " (" + __("Account") + ")";
'''
NEW_P = '''  print_order(data) {
    if (this.group_items_by_order) return RM_print_ticket(data.order_name || data.name);
    return frappe.call("restaurant_management.house.ticket_order", { identifier: data.name })
      .then(({ message }) => message && RM_print_ticket(message));
  }

  print_order_unused(data) {
    const title = data.name + " (" + __("Account") + ")";
'''
if OLD_P not in psrc:
    raise SystemExit("ticket print: print_order anchor not found")
open(PROCESS, "w").write(psrc.replace(OLD_P, NEW_P, 1))

osrc = open(ORDER).read()
OLD_O = '''  print_account() {
    const title = this.data.name + " (" + __("Account") + ")";
'''
NEW_O = '''  print_account() {
    return RM_print_ticket(this.data.name);
  }

  print_account_unused() {
    const title = this.data.name + " (" + __("Account") + ")";
'''
if OLD_O not in osrc:
    raise SystemExit("ticket print: print_account anchor not found")
open(ORDER, "w").write(osrc.replace(OLD_O, NEW_O, 1))
print("ticket print: kitchen ticket and table bill open the print view")
