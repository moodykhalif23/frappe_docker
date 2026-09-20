# rm_kot_round_stamp — stamp each trip to the kitchen with a round number.
#
# The board pairs with this (kot_rounds_board.py): it groups by "<order>::<round>"
# so every fire is its own ticket. Here we only record WHICH fire a line went out
# on, and — the dangerous half — make sure that stamp survives.
#
# Table Order.before_save calls items_list() then calculate_order(), and
# calculate_order does `self.entry_items = []` and re-appends every child row
# from an explicit kwarg list. EVERY save of a check rebuilds all of its rows.
# A field that is not carried through BOTH of those is silently destroyed the
# next time anyone touches the check. set_queue_items() makes it worse: its rows
# come from the client, which will never carry the field at all, so there is a
# fallback to the value already in the database.
#
# The stamp itself is deliberately NOT gated on the Restaurant Object switch —
# only on the column existing. Rounds are recorded whatever the board is doing,
# so the switch can be flipped on mid-service and mean something immediately,
# and flipped off without losing the history.
import ast

P = ('apps/restaurant_management/restaurant_management/restaurant_management/'
     'doctype/table_order/table_order.py')
GUARD = "rm_kot_round_stamp"

s = open(P).read()
if GUARD in s:
    print("kot_rounds_order: already present")
    raise SystemExit(0)

# ---------------------------------------------------------------- helper -----
A = 'status_attending = "Attending"\n'
assert s.count(A) == 1, "status_attending anchor %d" % s.count(A)
s = s.replace(A, A + '''
# rm_kot_round_stamp
import time as _rm_time

_RM_KOT_COL = {"ok": False, "at": 0.0}


_RM_FLOW = ["Sent", "Processing", "Completed", "Delivered"]


def _rm_keep_status(entry_item, was):
    """rm_kot_round_stamp: once a line has been fired, the ROW owns its status.

    Every save of a check rebuilds its rows from a snapshot the caller took
    earlier, sometimes in a browser minutes ago. Letting that snapshot write the
    status back is how a ticket the chef has already started cooking jumps
    backwards on the board."""
    seen = (was or {}).get("status")
    if seen and seen != status_attending:
        return seen
    want = entry_item.get("status")
    return status_attending if want in ("Pending", "", None) else want


def _rm_has_kot_round():
    """The column is created by a post-deploy step that runs after the container
    is already serving. Until it lands, every path here behaves as it did
    before. Positives are cached; negatives re-probed at most once a minute."""
    if _RM_KOT_COL["ok"]:
        return True
    now = _rm_time.time()
    if now - _RM_KOT_COL["at"] < 60:
        return False
    _RM_KOT_COL["at"] = now
    try:
        _RM_KOT_COL["ok"] = "kot_round" in frappe.db.get_table_columns("Order Entry Item")
    except Exception:
        _RM_KOT_COL["ok"] = False
    return _RM_KOT_COL["ok"]
''', 1)

# --------------------------------------------- carry it out of the doc --------
B = '''                row["order_name"] = item.parent
                row["entry_name"] = item.name'''
assert s.count(B) == 1, "items_list anchor %d" % s.count(B)
s = s.replace(B, '''                row["order_name"] = item.parent
                row["entry_name"] = item.name
                # rm_kot_round_stamp: items_list() is what before_save feeds to
                # calculate_order(), which rebuilds every row from it
                row["kot_round"] = item.get("kot_round") or 0''', 1)

# ------------------------------------------- and back in through the rebuild --
C = '''    def calculate_order(self, items, save=False):
        entry_items = {item["identifier"]: item for item in items}
        invoice = self.get_invoice(entry_items)

        self.entry_items = []'''
assert s.count(C) == 1, "calculate_order anchor %d" % s.count(C)
s = s.replace(C, '''    def calculate_order(self, items, save=False):
        entry_items = {item["identifier"]: item for item in items}
        invoice = self.get_invoice(entry_items)

        # rm_kot_round_stamp: this method DESTROYS and re-creates every child
        # row. set_queue_items() calls it with rows that came from the browser,
        # which carry no round at all, so fall back to what is already stored —
        # otherwise editing the pad would un-fire every ticket on the board.
        # rm_kot_round_stamp: what the ROWS say, read once. Three fields here must
        # come from the database and never from the caller's copy:
        #   status    - the caller's copy can be older than the chef's last press,
        #               and writing it back drags a round backwards on the kitchen
        #               board, the exact bug this change exists to end.
        #   kot_round - the client has never heard of it.
        #   waiter    - house.dispatch stamps WHO fired each line and then calls
        #               send(), whose save() lands here. Measured on the live site
        #               before this fix: 96 fired lines, 0 with a waiter on them.
        prior = {}
        if self.name:
            _cols = ["identifier", "status"]
            if _rm_has_kot_round():
                _cols.append("kot_round")
            if frappe.db.has_column("Order Entry Item", "waiter"):
                _cols.append("waiter")
            for _r in (frappe.db.sql(
                    "select %s from `tabOrder Entry Item` where parenttype='Table Order' "
                    "and parent=%%s" % ", ".join("`%s`" % c for c in _cols),
                    self.name, as_dict=True) or []):
                prior[_r["identifier"]] = _r
        _was = lambda _i: prior.get(_i) or {}

        self.entry_items = []''', 1)


# ------------------------------- the row, not the snapshot, owns the status ---
S = """                status="Attending" if entry_item["status"] in [
                    "Pending", "", None] else entry_item["status"],
"""
assert s.count(S) == 1, "calculate_order status anchor %d" % s.count(S)
s = s.replace(S, "", 1)

D = '''                is_customizable=entry_item["is_customizable"],
            ))'''
assert s.count(D) == 1, "append anchor %d" % s.count(D)
s = s.replace(D, '''                is_customizable=entry_item["is_customizable"],
                kot_round=frappe.utils.cint(  # rm_kot_round_stamp
                    _was(entry_item["identifier"]).get("kot_round")
                    or entry_item.get("kot_round") or 0),
                waiter=_was(entry_item["identifier"]).get("waiter"),  # rm_kot_round_stamp
                status=_rm_keep_status(  # rm_kot_round_stamp
                    entry_item, _was(entry_item["identifier"])),
            ))''', 1)

# ------------------------------------------------ a single-row edit path ------
E = '''                is_customizable=entry.get("is_customizable") or 0,
            )

            self.validate()'''
assert s.count(E) == 1, "update_item anchor %d" % s.count(E)
s = s.replace(E, '''                is_customizable=entry.get("is_customizable") or 0,
            )

            # rm_kot_round_stamp: only ever WRITE a round that was handed to us
            # (divide() copies one across). Including the key unconditionally
            # would let a client payload zero the stamp on a fired line, because
            # the branch below set_value()s this whole dict over the row.
            _rnd = frappe.utils.cint(entry.get("kot_round"))
            if _rnd and _rm_has_kot_round():
                data["kot_round"] = _rnd

            self.validate()''', 1)

# --------------------------------------------- a split keeps its round --------
F = '''                    status=item.status,
                    identifier=item.identifier if rest == 0 else divide_item["identifier"],'''
assert s.count(F) == 1, "divide anchor %d" % s.count(F)
s = s.replace(F, '''                    status=item.status,
                    # rm_kot_round_stamp: a divided copy of a fired dish belongs
                    # to the round it was fired in, not to a new one
                    kot_round=item.get("kot_round") or 0,
                    identifier=item.identifier if rest == 0 else divide_item["identifier"],''', 1)

# ------------------------------ a save must not blind the kitchen ------------
B2 = """        entry_items = self.items_list()

        if len(entry_items) > 0:
            self.calculate_order(entry_items)"""
assert s.count(B2) == 1, "before_save anchor %d" % s.count(B2)
s = s.replace(B2, B2 + """

        # rm_kot_round_stamp: a save must never take a check off the kitchen
        # board while food on it is still outstanding. The pad's copy of the
        # CHECK status can be older than the chef's last press, and the board
        # filters checks on exactly this field — a stale write here makes fired
        # food disappear from the kitchen screen with nothing to show for it.
        if self.status not in ("Invoiced", "Cancelled"):
            _live = [i.status for i in self.entry_items
                     if (i.qty or 0) > 0 and i.status in _RM_FLOW]
            if _live and self.status not in _RM_FLOW:
                self.status = min(_live, key=_RM_FLOW.index)""", 1)

# ------------------------------------------------------------- the fire -------
G = '''    @property
    def send(self):
        table = self._table
        items_to_return = []
        data_to_send = []
        for i in self.entry_items:
            item = frappe.get_doc("Order Entry Item", {"identifier": i.identifier})
            if item.status == status_attending:
                items_to_return.append(i.identifier)

                item.status = "Sent"
                item.ordered_time = frappe.utils.now_datetime()
                item.save()'''
assert s.count(G) == 1, "send anchor %d" % s.count(G)
s = s.replace(G, '''    def _rm_next_kot_round(self):
        """rm_kot_round_stamp: the number of this trip to the kitchen.

        Taken under a row lock on the check. Two tills firing the same check at
        the same moment are serialised by it: the second sees the first's round
        and takes the next one, so two fires make two cards — which is the
        truth. The lock also keeps this path and the chef's press taking their
        locks in the same order (check first, then lines); reversed, they
        deadlock, and house.dispatch has no retry wrapper to save the waiter."""
        if not _rm_has_kot_round():
            return 0
        frappe.db.sql("select name from `tabTable Order` where name = %s for update",
                      self.name)
        last = frappe.db.sql(
            "select max(kot_round) from `tabOrder Entry Item` "
            "where parenttype = 'Table Order' and parent = %s", self.name)
        return int((last and last[0] and last[0][0]) or 0) + 1

    @property
    def send(self):
        table = self._table
        items_to_return = []
        data_to_send = []
        kot_round = None
        for i in self.entry_items:
            item = frappe.get_doc("Order Entry Item", {"identifier": i.identifier})
            if item.status == status_attending:
                # rm_kot_round_stamp: inside the guard on purpose — send is a
                # @property, and a stray attribute access must not burn a round
                if kot_round is None:
                    kot_round = self._rm_next_kot_round()
                items_to_return.append(i.identifier)

                item.status = "Sent"
                item.ordered_time = frappe.utils.now_datetime()
                if kot_round:
                    item.kot_round = kot_round
                item.save()''', 1)

ast.parse(s)
assert s.count(GUARD) >= 7, "guard count %d" % s.count(GUARD)
open(P, "w").write(s)
print("kot_rounds_order: patched")
