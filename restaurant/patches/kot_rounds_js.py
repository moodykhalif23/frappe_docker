# rm_kot_rounds_js — the kitchen board, once a ticket is a fired ROUND.
#
# Three things the board cannot do as written:
#
# 1. The incremental splice (check_items) assumes ONE card per check — it is
#    handed a single order's payload and renders it as one group. It has no way
#    to express several cards for one check, and a card whose round has retired
#    would simply never be visited. With rounds on, coalesce into one refetch of
#    the whole board instead. Correct by construction, ~250ms behind at worst.
#
# 2. delete_order is only reachable for a group PRESENT in the payload
#    (render_group_container iterates the payload, not the screen), so a retired
#    round's card would sit there with every dish still legible. On a kitchen
#    screen a dead card is a re-cook instruction. Prune what the server stopped
#    sending.
#
# 3. time_elapsed() re-arms itself with setTimeout and is called from
#    make_food_commands, so every reload starts ANOTHER self-perpetuating clock
#    chain. That is already true today; with a reload on every fire and every
#    press it would compound through a service until the board crawls.
import subprocess

RM = 'apps/restaurant_management/restaurant_management'
P = RM + '/public/restaurant/js/process-manage-class.js'
PAY = RM + '/public/restaurant/js/pay-form-class.js'
GUARD = "rm_kot_rounds_js"

s = open(P).read()
if GUARD in s:
    print("kot_rounds_js: already present")
else:
    # ------------------------------------------------------------ the flag ---
    A = "  get group_items_by_order() {"
    assert s.count(A) == 1, "getter anchor %d" % s.count(A)
    s = s.replace(A, """  // rm_kot_rounds_js: exactly the value the server branched on — it ships the
  // column probe and the switch already resolved, so the two cannot disagree
  get kot_rounds() {
    return this.group_items_by_order && this.table.data.kot_rounds === 1;
  }

  soon() {
    clearTimeout(this._rm_soon);
    this._rm_soon = setTimeout(() => this.reload(false), 250);
  }

  prune_groups(payload) {
    // a card the server has stopped sending is finished work; on a kitchen
    // screen leaving it up is an instruction to cook it again
    const live = new Set(Object.keys(payload || {}));
    Object.keys(this.orders || {}).forEach(key => {
      if (live.has(key)) return;
      $(this.command_container()).find(`[data-group="${key}"]`).remove();
      delete this.orders[key];
    });

    const keep = new Set();
    Object.values(payload || {}).forEach(g => (g.items || []).forEach(i => keep.add(i.identifier)));
    Object.keys(this.items || {}).forEach(id => {
      if (!keep.has(id)) this.items[id].remove();
    });
  }

""" + A, 1)

    # ---------------------------------------------- one refetch, not a splice --
    B = """  check_items(items) {
    if (Array.isArray(items.items)) {"""
    assert s.count(B) == 1, "check_items anchor %d" % s.count(B)
    s = s.replace(B, """  check_items(items) {
    // rm_kot_rounds_js: this path renders ONE card for the order it was handed.
    // With a card per fired round it cannot say what it needs to say, so ask
    // the server for the whole board instead — coalesced, so a burst of
    // realtime events costs one call.
    if (this.kot_rounds) return this.soon();

    if (Array.isArray(items.items)) {""", 1)

    # ------------------------------------------------------------- the prune --
    C = """  make_food_commands(items = {}) {
    this.render_group_container(items);"""
    assert s.count(C) == 1, "make_food_commands anchor %d" % s.count(C)
    s = s.replace(C, """  make_food_commands(items = {}) {
    if (this.kot_rounds) this.prune_groups(items);  // rm_kot_rounds_js
    this.render_group_container(items);""", 1)

    # ----------------------------------------------- print THIS round only ----
    D = "    if (this.group_items_by_order) return RM_print_ticket(data.order_name || data.name, true);"
    assert s.count(D) == 1, "print anchor %d" % s.count(D)
    s = s.replace(D, """    // rm_kot_rounds_js: a round card that printed the whole check would hand the
    // pass food that is already on the table, as a cook instruction
    if (this.group_items_by_order) return RM_print_ticket(data.order_name || data.name, true, data.kot_round);""", 1)

    # --------------------------------------------- stop lying about success ---
    E = """      args: {
        identifier: data.name
      },
      always: () => {
        RM.ready(false, "success");
      },"""
    assert s.count(E) == 1, "execute anchor %d" % s.count(E)
    s = s.replace(E, """      args: {
        identifier: data.name
      },
      always: (r) => {
        // rm_kot_rounds_js: every recovery path on the server is a throw, and
        // this used to report success whatever came back
        if (r && r.exc) {
          RM.ready(false);
          RM.notification("red", "That ticket could not be updated");
          this.reload(false);
          return;
        }
        RM.ready(false, "success");
      },""", 1)

    # ------------------------------------------------------- one clock, not N --
    F = """    setTimeout(() => this.time_elapsed(), 3000);
  }"""
    assert s.count(F) == 1, "clock anchor %d" % s.count(F)
    s = s.replace(F, """    // rm_kot_rounds_js: this method re-arms itself AND is called from
    // make_food_commands, so every reload used to start another clock chain
    clearTimeout(this._rm_clock);
    this._rm_clock = setTimeout(() => this.time_elapsed(), 3000);
  }""", 1)

    # ------------------------------------------- the refresh must not block ---
    # get_commands_food opens with RM.working(), whose busy flag defaults TRUE,
    # and BOTH status buttons start with `if (RM.busy_message()) return;`. A
    # background refresh on every fire and every press would therefore bounce
    # the chef's taps with "please wait" all service. It is a refresh, not an
    # operation — say so.
    H1 = '    RM.working("Load commands food");'
    assert s.count(H1) == 1, "working anchor %d" % s.count(H1)
    s = s.replace(H1, '    RM.working("Load commands food", false);  // rm_kot_rounds_js: a refresh must never block the chef\'s buttons', 1)

    # ----------------------------------------- and a stale reply must not win --
    # Debouncing coalesces the triggers, not the replies. Two refreshes in
    # flight, the older one answering last, and the prune below would delete a
    # card the newer payload had just brought back.
    H2 = """  get_commands_food(clean = false) {"""
    assert s.count(H2) == 1, "get_commands anchor %d" % s.count(H2)
    s = s.replace(H2, """  get_commands_food(clean = false) {
    // rm_kot_rounds_js: NOT ++this._rm_gen — the field starts undefined, ++ gives
    // NaN, and NaN !== NaN would discard every payload and leave a blank board
    this._rm_gen = (this._rm_gen || 0) + 1;
    const gen = this._rm_gen;""", 1)
    H3 = """        setTimeout(() => {
          if (clean) {"""
    assert s.count(H3) == 1, "payload anchor %d" % s.count(H3)
    s = s.replace(H3, """        setTimeout(() => {
          if (gen !== this._rm_gen) return;  // rm_kot_rounds_js: a newer refresh already answered
          if (clean) {""", 1)

    # ------------------------------------- one board must not delete another's --
    # Kitchen and Bar can both be open in one session, and a round key is the
    # SAME string on both. A document-wide selector lets one centre's retirement
    # rip the other centre's card off the screen.
    H4 = """    const delete_order = (data) => {
      $(`[data-group="${data.name}"]`).remove();"""
    assert s.count(H4) == 1, "delete_order anchor %d" % s.count(H4)
    s = s.replace(H4, """    const delete_order = (data) => {
      // rm_kot_rounds_js: this board's card, not every board's
      $(this.command_container()).find(`[data-group="${data.name}"]`).remove();""", 1)

    H5 = """  get_field(group, field) {
    return $(`[data-name="${field}"]`, `[data-group="${group.name}"]`);
  }"""
    assert s.count(H5) == 1, "get_field anchor %d" % s.count(H5)
    s = s.replace(H5, """  get_field(group, field) {
    // rm_kot_rounds_js: scoped to this board — Kitchen and Bar share card keys
    return $(this.command_container()).find(`[data-group="${group.name}"] [data-name="${field}"]`);
  }""", 1)

    # ------------------------------------------- a dish must follow its card ---
    H6 = """      items.forEach((item) => {
        if (Object.keys(this.items).includes(item.identifier)) {
          this.items[item.identifier].data = item;
          this.items[item.identifier].render();
        } else {
          this.add_item(item, order);
        }"""
    assert s.count(H6) == 1, "reuse anchor %d" % s.count(H6)
    s = s.replace(H6, """      items.forEach((item) => {
        // rm_kot_rounds_js: a FoodCommand captures its card's container once and
        // never looks again. If the dish now belongs to a different card — the
        // rounds switch was flipped mid-service — reusing it writes the dish
        // into a card that is gone and leaves a revealed, empty one behind.
        const current = this.items[item.identifier];
        if (current && this.group_items_by_order &&
            (current.data || {}).order_name !== item.order_name) {
          current.remove();
        }
        if (this.items[item.identifier]) {
          this.items[item.identifier].data = item;
          this.items[item.identifier].render();
        } else {
          this.add_item(item, order);
        }"""[0:], 1)

    assert s.count(GUARD) >= 6, "guard count %d" % s.count(GUARD)
    open(P, 'w').write(s)
    print("kot_rounds_js: process-manage patched")

# ------------------------------------------------- the round on the print URL --
t = open(PAY).read()
if 'params.set("kot_round"' in t:
    print("kot_rounds_js: pay-form already present")
else:
    G = "window.RM_print_ticket = function (order_name, kitchen) {"
    assert t.count(G) == 1, "pay sig anchor %d" % t.count(G)
    t = t.replace(G, "window.RM_print_ticket = function (order_name, kitchen, kot_round) {", 1)
    H = '  if (kitchen) params.set("kitchen", "1");'
    assert t.count(H) == 1, "pay params anchor %d" % t.count(H)
    t = t.replace(H, H + '\n'
                  '  // rm_kot_rounds_js: a kitchen ticket for ONE fired round. Presence, not\n'
                  '  // truthiness — round 0 is a real, printable round (every check already\n'
                  '  // open when rounds arrived sits in it), and `if (kot_round)` drops it,\n'
                  '  // which would silently print the whole check instead. Gated on the\n'
                  '  // kitchen copy too, so a customer bill can never be round-filtered.\n'
                  '  if (kitchen && kot_round !== undefined && kot_round !== null && kot_round !== "") {\n'
                  '    params.set("kot_round", String(kot_round));\n'
                  '  }', 1)
    # The Pay form carries a SECOND "Order" button (make_actions, "send_order").
    # It only ever wrote the CHECK's status and never touched a line. That was
    # survivable while the board filtered on the check alone; now that a ticket
    # is a round of fired LINES, a check sent from here would produce a card with
    # no dishes on it and the kitchen would see nothing at all — the very bug
    # this POS was called out for. Route it through the real fire path.
    J = '  send_order() {\n    frappe.confirm(__("This action sent all order to Production Center,<br><strong>Do you want to continue?</strong>"), () => {\n      frappe.db.set_value("Table Order", this.order.data.name, "status", "Sent");\n    });\n  }'
    assert t.count(J) == 1, 'send_order anchor %d' % t.count(J)
    t = t.replace(J, '  send_order() {\n    // rm_kot_rounds_js: fire the LINES, not just the check. Setting the check\'s\n    // status alone left every dish un-fired, so the kitchen board — which now\n    // filters on the line — had nothing to show.\n    frappe.confirm(__("This action sent all order to Production Center,<br><strong>Do you want to continue?</strong>"), () => {\n      frappeHelper.api.call({\n        model: "Table Order",\n        name: this.order.data.name,\n        method: "send",\n        args: {},\n        always: (r) => {\n          if (r && r.exc) {\n            RM.ready(false);\n            RM.notification("red", "The order was not sent");\n            return;\n          }\n          RM.ready("Order Placed", "success");\n        },\n      });\n    });\n  }', 1)

    open(PAY, 'w').write(t)
    print("kot_rounds_js: pay-form patched")

# --------------------------------- flipping the switch must redraw the board --
# reload(clean=true) is the only path that empties the container and the caches,
# and it was reached only when group_items_by_order changed. Toggling kot_rounds
# re-keys every card, so without this the board keeps the old keys and the kill
# switch — the whole rollback story — does nothing until someone reopens it.
OBJ = RM + '/public/restaurant/js/restaurant-object-class.js'
o = open(OBJ).read()
if 'rm_kot_rounds_js' in o:
    print("kot_rounds_js: object-class already present")
else:
    I1 = "            const last_group_by = this.data.group_items_by_order;"
    assert o.count(I1) == 1, "last_group_by anchor %d" % o.count(I1)
    o = o.replace(I1, I1 + "\n            const last_rounds = this.data.kot_rounds;  // rm_kot_rounds_js", 1)
    I2 = "              this.process_manage.reload(last_group_by !== this.data.group_items_by_order);"
    assert o.count(I2) == 1, "reload anchor %d" % o.count(I2)
    o = o.replace(I2, "              this.process_manage.reload(\n"
                      "                last_group_by !== this.data.group_items_by_order ||\n"
                      "                last_rounds !== this.data.kot_rounds);  // rm_kot_rounds_js", 1)
    open(OBJ, 'w').write(o)
    print("kot_rounds_js: object-class patched")

# ------------------------ a dish the kitchen has started is still voidable ----
# Until now an Order Entry Item only ever reached "Sent", so the pad's two
# whitelists never had to name anything past it. With progress living on the
# dishes they hold Processing / Completed / Delivered routinely, and both lists
# would silently withdraw things a waiter can do today: voiding a line off the
# bill, and typing a note on it. Neither is a change this feature is entitled to
# make.
ITEM_JS = RM + '/public/restaurant/js/order-item-class.js'
it = open(ITEM_JS).read()
if 'rm_kot_rounds_js' in it:
    print("kot_rounds_js: order-item already present")
else:
    K1 = '    this.status_enabled_for_delete = [this.attending_status, "Pending", "Sent", null, undefined, ""];'
    assert it.count(K1) == 1, "delete whitelist anchor %d" % it.count(K1)
    K1N = ('    // rm_kot_rounds_js: a line the kitchen has picked up could always be\n'
           '    // voided while it sat at "Sent"; rounds must not quietly take that away\n'
           '    this.status_enabled_for_delete = [this.attending_status, "Pending", "Sent",\n'
           '                                      "Processing", "Completed", "Delivered",\n'
           '                                      null, undefined, ""];')
    it = it.replace(K1, K1N, 1)
    K2 = '    "Sent": ["notes"],\n    "Processing": ["notes"]\n  }'
    assert it.count(K2) == 1, "editor fields anchor %d" % it.count(K2)
    K2N = ('    "Sent": ["notes"],\n'
           '    "Processing": ["notes"],\n'
           '    // rm_kot_rounds_js: a note is the one thing a waiter can still add once\n'
           '    // the kitchen is on it, and these two states are new to a LINE\n'
           '    "Completed": ["notes"],\n'
           '    "Delivered": ["notes"]\n'
           '  }')
    it = it.replace(K2, K2N, 1)
    open(ITEM_JS, 'w').write(it)
    print("kot_rounds_js: order-item patched")


for path in (P, PAY, OBJ, ITEM_JS):
    subprocess.run(["node", "--check", path], check=True)
print("kot_rounds_js: syntax ok")
