# Deleting a table relied on _delete being a @property, because the app's
# dispatcher returns getattr(doc, method) without calling it when no args are
# passed. That is far too subtle: reading an attribute deleted a row. Make
# _delete an ordinary method and have the caller pass args so it is invoked.
P = "apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_object/restaurant_object.py"
J = "apps/restaurant_management/restaurant_management/public/restaurant/js/restaurant-object-class.js"

src = open(P).read()
OLD = """    @ property
    def _delete(self):
        self.delete()"""
NEW = """    def _delete(self):
        self.delete()"""
if OLD in src:
    open(P, "w").write(src.replace(OLD, NEW, 1))
    print("table delete: _delete is now a method")
elif NEW in src:
    print("table delete: _delete already a method")
else:
    raise SystemExit("table delete: python anchor not found")

js = open(J).read()
CALL_OLD = """      method: "_delete",
      always: () => {"""
CALL_NEW = """      method: "_delete",
      args: {},
      always: () => {"""
if CALL_OLD in js:
    open(J, "w").write(js.replace(CALL_OLD, CALL_NEW, 1))
    print("table delete: caller now passes args so the method is invoked")
elif CALL_NEW in js:
    print("table delete: caller already passes args")
else:
    raise SystemExit("table delete: js anchor not found")
