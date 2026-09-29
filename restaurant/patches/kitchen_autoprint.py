# rm_kitchen_autoprint — pressing Send (the Order button) prints the kitchen
# ticket for the round it just fired, on the station that pressed it; and
# rm_kitchen_nudge — the order screen's back button asks before leaving a table
# with dishes nobody sent.
#
# Why: a kitchen ticket only ever printed when someone clicked the print icon on
# a card on the kitchen board. In the week to 29 Sep 2026 that happened zero
# times; 3 of ~400 checks were sent at all, and the kitchen cooked from shouts.
#
# 1. table_order.py `send` already knows which round it stamped (kot_round) but
#    returned only self.data(). It now adds rm_fired / rm_kot_round /
#    rm_print_kitchen to that dict. house.dispatch returns `doc.send`, so both
#    fire paths — the pad's Order button (dispatch) and the pay form's Order
#    button (api.call) — carry it without touching house.py.
# 2. RM_kitchen_autoprint(order, res) calls RM_print_ticket(order, true, round)
#    when the server says so. Round None means rounds are switched off: print the
#    whole check's kitchen copy, which is what the board's print icon does then.
# 3. Restaurant Settings > rm_print_kitchen_on_send switches it off without a
#    deploy. A site without the field reads as ON.
# 4. "Not yet" on the prompt always leaves: a prompt must never trap a waiter.

RM = 'apps/restaurant_management/restaurant_management'
TO = RM + '/restaurant_management/doctype/table_order/table_order.py'
PAY = RM + '/public/restaurant/js/pay-form-class.js'
TOC = RM + '/public/restaurant/js/table-order-class.js'
OM = RM + '/public/restaurant/js/order-manage-class.js'
GUARD = "rm_kitchen_autoprint"
NUDGE = "rm_kitchen_nudge"


def edit(path, guard, pairs, append=None):
    name = path.rsplit('/', 1)[-1]
    s = open(path).read()
    if guard in s:
        print("kitchen_autoprint: %s already present" % name)
        return
    for old, new, count in pairs:
        n = s.count(old)
        assert n == count, "%s: anchor seen %d times, want %d: %r" % (name, n, count, old[:70])
        s = s.replace(old, new)
    if append:
        s = s.rstrip("\n") + "\n\n\n" + append.strip("\n") + "\n"
    assert guard in s, "%s: guard missing after edit" % name
    open(path, 'w').write(s)
    print("kitchen_autoprint: patched %s" % name)


# ------------------------------------------------------------------ server ---
SEND_TAIL = '''        #self.synchronize_data = dict(status=["Sent"])
        self.synchronize(dict(status=["Sent"]))

        return self.data()
'''
SEND_TAIL_NEW = '''        #self.synchronize_data = dict(status=["Sent"])
        self.synchronize(dict(status=["Sent"]))

        # rm_kitchen_autoprint: tell the station that fired WHICH round it fired
        # and whether to print it. Printing is the station's job (the till's
        # kiosk Chrome prints silently); only the server knows what it stamped.
        out = self.data()
        out["rm_fired"] = len(items_to_return)
        out["rm_kot_round"] = kot_round or None
        out["rm_print_kitchen"] = 1 if items_to_return and _rm_print_kitchen_on_send() else 0
        return out
'''
SETTING_FN = '''
def _rm_print_kitchen_on_send():
    """rm_kitchen_autoprint: Restaurant Settings > Print kitchen ticket on Send.
    get_value, not get_single_value: a site without the field reads as ON
    instead of throwing in the middle of a fire."""
    try:
        v = frappe.db.get_value("Restaurant Settings", "Restaurant Settings",
                                "rm_print_kitchen_on_send")
    except Exception:
        return True
    return True if v in (None, "") else bool(frappe.utils.cint(v))
'''
edit(TO, GUARD, [(SEND_TAIL, SEND_TAIL_NEW, 1)], append=SETTING_FN)

# ------------------------------------------------------------------ client ---
PRINT_URL = 'window.RM_print_url = window.RM_print_url || function (url) {'
AUTOPRINT_FN = '''// rm_kitchen_autoprint: print the kitchen ticket for the round a Send just
// fired, when the server says so (Restaurant Settings > Print kitchen ticket on
// Send). Presence, not truthiness, for the round — see RM_print_ticket.
window.RM_kitchen_autoprint = function (order_name, res) {
  if (!order_name || !res || !res.rm_print_kitchen) return;
  const round = res.rm_kot_round;
  RM_print_ticket(order_name, true, (round === null || round === undefined) ? undefined : round);
};

''' + PRINT_URL
PAY_READY = '          RM.ready("Order Placed", "success");\n'
PAY_READY_NEW = PAY_READY + '          RM_kitchen_autoprint(this.order.data.name, r && r.message); // rm_kitchen_autoprint\n'
edit(PAY, GUARD, [(PRINT_URL, AUTOPRINT_FN, 1), (PAY_READY, PAY_READY_NEW, 1)])

PAD_FIRED = '''        this.check_items({ items: r.message.items });
      }).catch(() => RM.ready(false, "error"));'''
PAD_FIRED_NEW = '''        this.check_items({ items: r.message.items });
        RM_kitchen_autoprint(this.data.name, r.message); // rm_kitchen_autoprint
      }).catch(() => RM.ready(false, "error"));'''
edit(TOC, GUARD, [(PAD_FIRED, PAD_FIRED_NEW, 1)])

BACK = 'RMHelper.return_main_button(this.title, () => this.modal.hide()).html()'
BACK_NEW = 'RMHelper.return_main_button(this.title, () => this.rm_leave()).html()'
CLOSE = '''  close() {
    this.modal.hide()
  }
'''
LEAVE = '''  // rm_kitchen_nudge: the back button closed the table with dishes still
  // unsent, and the kitchen heard about them from a shout or not at all. Ask
  // once. "Not yet" always leaves: a prompt must never trap a waiter.
  rm_leave() {
    const leave = () => this.modal.hide();
    const order = this.current_order;
    let pending = 0;
    try { pending = (order && order.pending_count) || 0; } catch (e) { pending = 0; }
    if (!pending || (window.RM && RM.busy)) return leave();
    const d = new frappe.ui.Dialog({
      title: __("Send to the kitchen?"),
      fields: [{
        fieldtype: "HTML",
        options: `<p style="font-size:16px;margin:0">${__("{0} item(s) on this table have not been sent to the kitchen yet.", [pending])}</p>`
          + `<p style="margin:8px 0 0">${__("Send them now so the kitchen gets a ticket.")}</p>`,
      }],
      primary_action_label: __("Send now"),
      primary_action: () => { d.hide(); order.order(); },
      secondary_action_label: __("Not yet"),
      secondary_action: () => { d.hide(); leave(); },
    });
    d.show();
  }

''' + CLOSE
edit(OM, NUDGE, [(BACK, BACK_NEW, 2), (CLOSE, LEAVE, 1)])
