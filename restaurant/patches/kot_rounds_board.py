# rm_kot_rounds_board — a fired ROUND is a kitchen ticket, not the whole check.
#
# Before: the board grouped Order Entry Items by their parent Table Order and
# the chef's button advanced the Table Order's own status. Firing an addition
# therefore dragged a ticket the chef had already moved to Processing back to
# "Sent", and there was no way to tell the new dishes from the ones already
# cooked. Progress lived on the check; it belongs on the dishes.
#
# After: each fire stamps an integer kot_round on the lines it sends (see
# kot_rounds_order.py). The board groups by "<order>::<round>", so each fire is
# its own card with its own lifecycle, and the press advances only that round's
# lines for THIS production centre. Table Order.status becomes a roll-up of the
# least advanced thing still outstanding, which keeps the floor plan, the POS
# and the board's parent whitelist working exactly as before.
#
# One switch, read once: Restaurant Object.kot_rounds. Off, or the column
# missing, and every path behaves exactly as it did before this patch.
import ast

P = ('apps/restaurant_management/restaurant_management/restaurant_management/'
     'doctype/restaurant_object/restaurant_object.py')
GUARD = "rm_kot_rounds_board"

s = open(P).read()
if GUARD in s:
    print("kot_rounds_board: already present")
    raise SystemExit(0)

# ---------------------------------------------------------------- helpers ---
A = "from frappe.utils import get_datetime\nfrom datetime import timedelta\n"
assert s.count(A) == 1, "import anchor %d" % s.count(A)
HELPERS = A + '''
import time as _rm_time

# rm_kot_rounds_board
_RM_KOT_SEP = "::"
_RM_KOT_COL = {"ok": False, "at": 0.0}


def _rm_has_kot_round():
    """The kot_round column is created by a post-deploy step that runs after the
    container is already serving, so this code must survive its own absence and
    simply behave as it did before. Positives are cached for the life of the
    worker; negatives are re-probed at most once a minute."""
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


def _rm_kot_key(parent, rnd):
    return "%s%s%d" % (parent, _RM_KOT_SEP, int(rnd or 0))


def _rm_kot_split(identifier):
    """"<order>::<round>" -> (order, round). Anything else is not a round key."""
    parent, sep, rnd = (identifier or "").rpartition(_RM_KOT_SEP)
    if not sep:
        return identifier, None
    try:
        return parent, int(rnd)
    except ValueError:
        return identifier, None


def _rm_rank(statuses):
    return {s: n for n, s in enumerate(statuses)}


def _rm_least_advanced(values, flow):
    """The status of a ticket is the least advanced status on it: a card cannot
    be cooked while one of its own dishes is still waiting."""
    rank = _rm_rank(flow)
    live = [v for v in values if v in rank]
    if not live:
        return None
    return min(live, key=lambda v: rank[v])
'''
s = s.replace(A, HELPERS, 1)

# ------------------------------------------------- the board's line filter ---
B = """            if self.group_items_by_order == 1:
                parent_filter["status"] = ("in", status_managed if len(
                    status_managed) > 0 else [random_string])
            else:"""
assert s.count(B) == 1, "filter anchor %d" % s.count(B)
s = s.replace(B, """            if self.group_items_by_order == 1:
                parent_filter["status"] = ("in", status_managed if len(
                    status_managed) > 0 else [random_string])
                # rm_kot_rounds_board: a round is a ticket, so only lines this
                # centre has actually been sent belong on the board. Without
                # this a card would carry dishes the waiter has keyed but not
                # fired, and the chef would cook food nobody ordered yet.
                if self._kot_rounds:
                    filters["status"] = ("in", status_managed if len(
                        status_managed) > 0 else [random_string])
            else:""", 1)

# ------------------------------------------------------ grouping by round ---
C = '''        if self.group_items_by_order == 1:
            for group in groups:
                order = frappe.get_doc("Table Order", group)
                groups[group].update(dict(data=order.short_data()["data"]))

        return groups'''
assert s.count(C) == 1, "commands_food anchor %d" % s.count(C)
s = s.replace(C, '''        if self.group_items_by_order == 1:
            # rm_kot_rounds_board: one short_data() per CHECK, not per card —
            # with rounds a check can own several cards and short_data is not
            # cheap (it counts rows and reads the delivery address).
            cache = {}
            for group in groups:
                parent, rnd = _rm_kot_split(group) if self._kot_rounds else (group, None)
                if parent not in cache:
                    cache[parent] = frappe.get_doc("Table Order", parent).short_data()["data"]
                data = cache[parent]
                if rnd is not None:
                    data = self._rm_round_data(data, group, parent, rnd, groups[group]["items"])
                groups[group].update(dict(data=data))

        return groups

    def _rm_round_data(self, base, key, parent, rnd, items):
        """rm_kot_rounds_board: the card for ONE fired round of a check.

        Everything the board reads by name comes from here: `name` is what the
        card's data-group attribute and the chef's button both use, so it has to
        be the composite key; `order_name` stays the real Table Order because
        that is what gets printed and billed."""
        data = dict(base)
        flow = self._status_managed
        status = _rm_least_advanced([i.get("status") for i in items], flow) or base.get("status")
        times = [i.get("ordered_time") for i in items if i.get("ordered_time")]
        try:
            psd = self.process_status_data(frappe._dict(status=status))
        except Exception:
            # an unknown status must not blank the whole kitchen screen
            psd = base.get("process_status_data")
        data.update(dict(
            name=key,
            order_name=parent,
            kot_round=rnd,
            status=status,
            items_count=len(items),
            process_status_data=psd,
            # the clock on the card is this round's, so it restarts when the
            # round is fired instead of counting from when the table sat down
            ordered_time=min(times) if times else base.get("ordered_time"),
        ))
        return data

    def _rm_set_round_status(self, identifier):
        """rm_kot_rounds_board: advance ONE round of ONE check, for THIS centre.

        Only the lines sitting at the round's least advanced status move, so a
        dish fired thirty seconds ago can never be marked cooked on the back of
        a press meant for the dishes before it."""
        parent, rnd = _rm_kot_split(identifier)

        # Lock the CHECK first, before touching a single line — the same order
        # TableOrder.send takes them in. The fire path locks the parent then
        # writes its lines; if a press wrote lines and then reached for the
        # parent, the two would deadlock, and house.dispatch has no retry
        # wrapper, so the waiter would be told nothing was sent. The lock also
        # serialises presses on one check, so Kitchen and Bar cannot race each
        # other on the roll-up.
        frappe.db.sql("select name from `tabTable Order` where name = %s for update", parent)

        flow = self._status_managed
        groups = self._items_group
        rows = frappe.db.get_all("Order Entry Item", fields=["name", "status"], filters={
            "parenttype": "Table Order",
            "parent": parent,
            "kot_round": rnd,
            "qty": (">", 0),
            "item_group": ("in", groups if len(groups) > 0 else [""]),
            "status": ("in", flow if len(flow) > 0 else [""]),
        })
        if not rows:
            frappe.throw(_("That ticket has already left the board"))

        last_status = _rm_least_advanced([r.status for r in rows], flow)
        status = self.next_status(last_status)

        for row in rows:
            if row.status == last_status:
                frappe.db.set_value("Order Entry Item", row.name, "status", status,
                                    update_modified=False)

        order = frappe.get_doc("Table Order", parent)
        self._rm_rollup(order)
        order.reload()
        order.synchronize(dict(status=[last_status, status]))

    def _rm_rollup(self, order):
        """rm_kot_rounds_board: the check shows the least advanced thing still
        outstanding on it, across every centre.

        This is load-bearing three times over: it keeps the floor plan and the
        POS meaning something now that progress lives on the dishes; it keeps
        the check inside the board's parent whitelist while ANY round is live;
        and it bumps the parent's modified, so a stale concurrent save fails
        loudly instead of silently dragging a round back to Sent."""
        if order.status in ("Invoiced", "Cancelled"):
            return
        flow = list(self._status_managed)
        if flow:
            tail = self.next_status(flow[-1])
            if tail and tail not in flow:
                flow.append(tail)
        rows = frappe.db.get_all("Order Entry Item", fields=["status"], filters={
            "parenttype": "Table Order", "parent": order.name, "qty": (">", 0)})
        want = _rm_least_advanced([r.status for r in rows], flow)
        if want and want != order.status:
            # update_modified=False on purpose. Bumping it would make every chef
            # press abort whatever pad request was in flight on that check, and
            # the waiter would lose the dish they had just tapped. The round data
            # does not need that guard any more: line status is now read from the
            # row, so a stale save cannot move a fired line at all.
            frappe.db.set_value("Table Order", order.name, "status", want,
                                update_modified=False)''', 1)

# ------------------------------------------------ the badge on the tile -------
# The Kitchen tile's number is how a chef with the board closed learns work has
# arrived. Counting distinct CHECKS means a second round landing on a check the
# badge has already counted moves nothing, so the one signal that says "come and
# look" goes quiet exactly when a table adds to its order.
H = """        if self.group_items_by_order == 1:
            return len(frappe.db.get_all(
                "Order Entry Item",
                fields="name",
                filters=filters,
                group_by="parent"
            ))"""
assert s.count(H) == 1, "orders_count anchor %d" % s.count(H)
s = s.replace(H, """        if self.group_items_by_order == 1:
            return len(frappe.db.get_all(
                "Order Entry Item",
                fields="name",
                filters=filters,
                # rm_kot_rounds_board: tickets, not checks
                group_by="parent, kot_round" if self._kot_rounds else "parent"
            ))""", 1)

# ------------------------------------------- the key the board groups under ---
D = "            order_name=entry.identifier if self.group_items_by_order != 1 else entry.parent,"
assert s.count(D) == 1, "order_name anchor %d" % s.count(D)
s = s.replace(D, """            # rm_kot_rounds_board: the board matches an item's order_name against
            # the card's data-group, so with rounds on it must be the round key
            order_name=(entry.identifier if self.group_items_by_order != 1 else (
                _rm_kot_key(entry.parent, entry.get("kot_round")) if self._kot_rounds
                else entry.parent)),
            kot_round=entry.get("kot_round") or 0,""", 1)

# -------------------------------------------------------- the chef's press ---
E = """    def set_status_command(self, identifier):
        if self.group_items_by_order == 1:"""
assert s.count(E) == 1, "set_status anchor %d" % s.count(E)
s = s.replace(E, """    def set_status_command(self, identifier):
        # rm_kot_rounds_board: with rounds on the identifier is "<order>::<round>"
        # and the press belongs to that round alone.
        if self._kot_rounds and _RM_KOT_SEP in (identifier or ""):
            return self._rm_set_round_status(identifier)

        if self.group_items_by_order == 1:""", 1)

# ---------------------------------------------- the flag, and the client's ---
F = '''        if self.type == "Production Center":
            data["status_managed"] = self._status_managed'''
assert s.count(F) == 1, "get_data anchor %d" % s.count(F)
s = s.replace(F, '''        if self.type == "Production Center":
            data["status_managed"] = self._status_managed
            # rm_kot_rounds_board: the client must branch on exactly the value
            # the server branched on, column probe included
            data["kot_rounds"] = 1 if self._kot_rounds else 0''', 1)

G = """    @ property
    def _status_managed(self):"""
assert s.count(G) == 1, "_status_managed anchor %d" % s.count(G)
s = s.replace(G, """    @ property
    def _kot_rounds(self):
        \"\"\"rm_kot_rounds_board: one read, whole feature. Read path, write path
        and the fire-time stamp all branch on this, so the feature can only be
        fully on or fully off — never half applied.\"\"\"
        return bool(
            self.group_items_by_order == 1
            and frappe.utils.cint(self.get("kot_rounds")) == 1
            and _rm_has_kot_round()
        )

    @ property
    def _status_managed(self):""", 1)

ast.parse(s)
assert s.count(GUARD) >= 8, "guard count %d" % s.count(GUARD)
open(P, "w").write(s)
print("kot_rounds_board: patched")
