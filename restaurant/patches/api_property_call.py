# api.call() invokes whatever getattr returns. TableOrder.send is a @property —
# getattr fires the dispatch and hands back data, which then gets *called*:
# "'dict' object is not callable", seen on live under concurrent firing.
P = "apps/restaurant_management/restaurant_management/api.py"

src = open(P).read()
# the retry wrapper writes the same guard with a different lead-in
if "not callable(attr)" in src:
    print("api property: already applied")
    raise SystemExit

OLD = """        kwargs = {arg: _args[arg] for arg in _args}
        return getattr(doc, method)(**kwargs)"""
NEW = """        kwargs = {arg: _args[arg] for arg in _args}
        attr = getattr(doc, method)
        if not callable(attr):
            return attr
        return attr(**kwargs)"""

if OLD not in src:
    raise SystemExit("api property: anchor not found in api.py")
open(P, "w").write(src.replace(OLD, NEW, 1))
print("api property: only callables get called")
