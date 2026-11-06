# rm_kitchen_stock: a paid bill takes its portions out of the kitchen's stock.
#
# The issue runs in the background just after the bill commits (inventory.queue_consumption),
# so stock can never slow down or fail a payment; a voided bill puts its portions back
# (reverse_invoice), and a sweep every 10 minutes catches any bill whose issue never ran.
import sys

sys.path.insert(0, "/tmp")
from _patchlib import once  # noqa: E402

HOOKS = "apps/restaurant_management/restaurant_management/hooks.py"


def hooks(s):
	return s.rstrip("\n") + '''

# rm_kitchen_stock: a paid bill takes its portions out of kitchen stock, a voided one puts them back
doc_events = globals().get("doc_events") or {}
_ks_ev = doc_events.setdefault("POS Invoice", {})
for _ks_key, _ks_method in (("on_submit", "restaurant_management.inventory.queue_consumption"),
                            ("on_cancel", "restaurant_management.inventory.reverse_invoice")):
    _ks_cur = _ks_ev.get(_ks_key) or []
    _ks_cur = [_ks_cur] if isinstance(_ks_cur, str) else list(_ks_cur)
    if _ks_method not in _ks_cur:
        _ks_cur.append(_ks_method)
    _ks_ev[_ks_key] = _ks_cur
scheduler_events = globals().get("scheduler_events") or {}
_ks_cron = scheduler_events.setdefault("cron", {}).setdefault("*/10 * * * *", [])
if "restaurant_management.inventory.sweep" not in _ks_cron:
    _ks_cron.append("restaurant_management.inventory.sweep")
'''


once(HOOKS, "rm_kitchen_stock", hooks, "kitchen stock: hooks")
