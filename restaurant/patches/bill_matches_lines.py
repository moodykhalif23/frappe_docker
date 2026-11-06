# rm_atomic_item_write + rm_bill_waits_for_writes — a printed bill must add up.
#
# Reported 6 Nov 2026 (OR-2026-03071): the bill listed Special Tea 2 x 300,
# Rolex 200, Samosa Pair 120 — lines adding to 620 — under "Total Sh 470.00".
# The pad showed 620. Over the six days of nginx log then on hand, 11 of 417
# bills printed this way, every one within a second of a +/- on a dish already
# on the check.
#
# How: a +/- on an existing line is push_item -> update_item, which writes the
# line with frappe.db.set_value and returns "db_commit"; db_commit() then
# COMMITTED, reloaded, and only then aggregate() recomputed Table Order.amount
# and saved — about a second later, since that save rebuilds the check through
# a full POS Invoice validate. Anything reading the check in between saw the
# new line under the old total. The Account button prints at once, so a bill
# pressed straight after a tap landed in that second.
#
# 1. server — db_commit() no longer commits. The line and the recomputed total
#    reach the database in the one commit frappe makes at the end of the
#    request. reload() still sees the line: it reads on this request's own
#    connection. divide() goes through the same method and gains the most: it
#    deleted a whole line from the old check and committed BEFORE adding it to
#    the new one, so a failure mid-split dropped the dish from both.
# 2. client — print_account() waits until every push_item / delete_item this
#    tablet sent for the check has come back, so the bill carries the last tap.
#    A write that never returns refuses the print after 15 s rather than print
#    a bill that is missing a dish.
# 3. the template (order_account_80mm.html, rm_bill_total_from_lines) prints
#    the sum of its own lines as the Total whenever nothing else goes into it.
#
# Idempotent: each file is guarded by a token only its applied edit contains,
# and the end state is asserted.

RM = 'apps/restaurant_management/restaurant_management'
TO = RM + '/restaurant_management/doctype/table_order/table_order.py'
ITEM = RM + '/public/restaurant/js/order-item-class.js'
TOC = RM + '/public/restaurant/js/table-order-class.js'
ATOMIC = "rm_atomic_item_write"
WAITS = "rm_bill_waits_for_writes"


def edit(path, guard, pairs):
    name = path.rsplit('/', 1)[-1]
    s = open(path).read()
    if guard in s:
        print("bill_matches_lines: %s already present" % name)
        return
    for old, new, count in pairs:
        n = s.count(old)
        assert n == count, "%s: anchor seen %d times, want %d: %r" % (name, n, count, old[:70])
        s = s.replace(old, new)
    assert guard in s, "%s: guard missing after edit" % name
    open(path, 'w').write(s)
    print("bill_matches_lines: patched %s" % name)


# ------------------------------------------------------------------ server ---
DB_COMMIT = '''    def db_commit(self):
        frappe.db.commit()
        self.reload()
        self.aggregate()
'''
DB_COMMIT_NEW = '''    def db_commit(self):
        # rm_atomic_item_write: no commit here. Committing the line before
        # aggregate() had recomputed the check's total let any reader in
        # between — the bill above all — see the new line under the old total
        # (6 Nov 2026: a bill for 470 under lines adding to 620). The line and
        # the total now land in the request's one commit. reload() still sees
        # the line: it reads on this request's own connection.
        self.reload()
        self.aggregate()
'''
edit(TO, ATOMIC, [(DB_COMMIT, DB_COMMIT_NEW, 1)])
s = open(TO).read()
start = s.index("    def db_commit(self):")
body = s[start:s.index("\n    def ", start + 1)]
assert "frappe.db.commit()" not in body, "db_commit still commits"

# ------------------------------------------------------------------ client ---
TRACKER = '''// rm_bill_waits_for_writes: the writes this tablet has sent to a check and
// not yet heard back about. The bill is read from the server, so a bill
// printed while a +/- is still on the wire is the check as it was before that
// tap; print_account() waits on settled() first.
window.RM_order_writes = window.RM_order_writes || {
  open: {},
  waiting: {},
  begin(order) {
    this.open[order] = (this.open[order] || 0) + 1;
    let ended = false;
    return {
      end: () => {
        if (ended) return;
        ended = true;
        this.open[order] -= 1;
        if (this.open[order] > 0) return;
        delete this.open[order];
        const waiting = this.waiting[order] || [];
        delete this.waiting[order];
        waiting.forEach(f => f());
      },
    };
  },
  pending(order) {
    return (this.open[order] || 0) > 0;
  },
  // true once nothing is in flight for this check; false after `ms`
  settled(order, ms = 15000) {
    if (!this.pending(order)) return Promise.resolve(true);
    return new Promise(resolve => {
      const timer = setTimeout(() => resolve(false), ms);
      (this.waiting[order] = this.waiting[order] || []).push(() => {
        clearTimeout(timer);
        resolve(true);
      });
    });
  },
};

class OrderItem {'''
CALL = '''    frappeHelper.api.call({
      model: "Table Order",
      name: this.order.data.name,
      method: this.data.qty > 0 ? "push_item" : "delete_item",
      args: { item: this.data.qty > 0 ? this.data : this.data.identifier },
      always: (r) => {
'''
CALL_NEW = '''    const rm_write = RM_order_writes.begin(this.order.data.name); // rm_bill_waits_for_writes
    frappeHelper.api.call({
      model: "Table Order",
      name: this.order.data.name,
      method: this.data.qty > 0 ? "push_item" : "delete_item",
      args: { item: this.data.qty > 0 ? this.data : this.data.identifier },
      always: (r) => {
        rm_write.end();
'''
edit(ITEM, WAITS, [("class OrderItem {", TRACKER, 1), (CALL, CALL_NEW, 1)])

PRINT = '''  print_account() {
    return RM_print_ticket(this.data.name);
  }
'''
PRINT_NEW = '''  print_account() {
    // rm_bill_waits_for_writes: print only once every +/- this tablet sent to
    // the check has landed, or the bill misses the last tap.
    const name = this.data.name;
    if (!RM_order_writes.pending(name)) return RM_print_ticket(name);
    frappe.show_alert({ indicator: "blue", message: __("Saving the last change, then printing the bill") });
    return RM_order_writes.settled(name).then(done => {
      if (done) return RM_print_ticket(name);
      frappe.msgprint({
        title: __("Bill not printed"),
        indicator: "orange",
        message: __("The last change to this check has not reached the server. Check the connection, then press Account again."),
      });
    });
  }
'''
edit(TOC, WAITS, [(PRINT, PRINT_NEW, 1)])

for path in (ITEM, TOC):
    assert WAITS in open(path).read(), "%s: %s missing" % (path, WAITS)
