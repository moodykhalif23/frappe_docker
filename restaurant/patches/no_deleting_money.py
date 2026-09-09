# A sale is voided by cancelling; deleting erases it and hands its number back.
H = "apps/restaurant_management/restaurant_management/hooks.py"
src = open(H).read()
if "rm_no_deleting_money" in src:
    print("no deleting money: hooks already applied")
else:
    src = src.rstrip("\n") + '''

# rm_no_deleting_money: a sale is voided by cancelling, never by deleting
doc_events = globals().get("doc_events") or {}
for _dt in ("POS Invoice", "Sales Invoice", "POS Closing Entry", "Table Order"):
    doc_events.setdefault(_dt, {})["on_trash"] = "restaurant_management.house.refuse_delete"
'''
    open(H, "w").write(src)
    print("no deleting money: on_trash guards registered")

N = "apps/frappe/frappe/model/naming.py"
nsrc = open(N).read()

# The first bake put the guard above the docstring, which stopped being one
STALE = '''def revert_series_if_last(key, name, doc=None):
	# rm_series_never_rewinds: handing a deleted number back makes the series unauditable
	for _p in ("ACC-PSINV-", "ACC-SINV-", "POS-CLO-", "OR-", "RES-BOOK-"):
		if _p in str(key or "") or str(name or "").startswith(_p):
			return

'''
if STALE in nsrc:
    nsrc = nsrc.replace(STALE, "def revert_series_if_last(key, name, doc=None):\n", 1)
    open(N, "w").write(nsrc)
    print("no deleting money: lifted the earlier guard back out of the docstring")

if "rm_series_never_rewinds" in nsrc:
    print("no deleting money: series guard already applied")
    raise SystemExit

# Both call sites pass a naming series or an autoname, and each starts with its prefix
GUARD = '''	# rm_series_never_rewinds: handing a deleted number back makes the series unauditable
	for _p in ("ACC-PSINV-", "ACC-SINV-", "POS-CLO-", "OR-", "RES-BOOK-"):
		if str(key or "").startswith(_p) or str(name or "").startswith(_p):
			return

'''
ANCHOR = '\tif ".#" in key:'
if nsrc.count(ANCHOR) != 1:
    raise SystemExit("no deleting money: revert_series_if_last anchor is not unique")
open(N, "w").write(nsrc.replace(ANCHOR, GUARD + ANCHOR, 1))
print("no deleting money: the series no longer rewinds for money documents")
