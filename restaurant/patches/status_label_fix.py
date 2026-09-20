# rm_status_labels — the kitchen board's pill for a fired ticket read "Whiting".
#
# It is the `message` on the "Sent" Status Order PC record, rendered by
# process_status_data() -> status_message on every card the chef looks at. Two
# places hold it: the seed in setup/install.py (only runs on a fresh install)
# and the live record itself, which is what anyone actually sees — house.py's
# _ensure_status_labels() corrects that one on every deploy.
import ast

P = "apps/restaurant_management/restaurant_management/setup/install.py"
GUARD = "rm_status_labels"

s = open(P).read()
if GUARD in s:
    print("status_label_fix: already present")
    raise SystemExit(0)

A = '''            action="Sent", icon="fa fa-paper-plane-o", color="steelblue",
            message="Whiting", action_message="Confirm", allows_to_edit_item="0"'''
assert s.count(A) == 1, "sent status anchor %d" % s.count(A)
s = s.replace(A, '''            action="Sent", icon="fa fa-paper-plane-o", color="steelblue",
            # rm_status_labels: the chef reads this on every fired ticket
            message="Waiting", action_message="Confirm", allows_to_edit_item="0"''', 1)

ast.parse(s)
assert GUARD in s
open(P, "w").write(s)
print("status_label_fix: patched")
