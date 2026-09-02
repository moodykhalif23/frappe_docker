# Every pad and board action funnels through api.call, and MariaDB aborts one of
# two conflicting writes with a deadlock. The floor saw "Deadlock Occurred" and,
# worse, silently kept the item queued: the cart showed a dish the check never
# saved, so Order stayed greyed and the dish could not be sent.
P = "apps/restaurant_management/restaurant_management/api.py"

src = open(P).read()
if "_call_with_retry" in src:
    print("deadlock retry: already applied")
    raise SystemExit

# The @property guard from an earlier patch is already in place on a rebake.
OLD = '''@frappe.whitelist()
def call(model, name, method, args=None):
    doc = frappe.get_doc(model, name)
    if args is not None:
        _args = json.loads(args)
        # args = [_args[arg] for arg in _args]
        kwargs = {arg: _args[arg] for arg in _args}
        attr = getattr(doc, method)
        if not callable(attr):
            return attr
        return attr(**kwargs)
    # return doc.run_method(method, **kwargs)
    else:
        return getattr(doc, method)'''

NEW = '''def _call_with_retry(model, name, method, kwargs, attempts=4):
    """Run one pad action, retrying the whole thing if the database deadlocks.

    MariaDB rolls the losing transaction back entirely, so re-running is safe —
    and far better than telling a waiter to try again while the item sits queued.
    """
    import time

    for attempt in range(attempts):
        try:
            doc = frappe.get_doc(model, name)
            attr = getattr(doc, method)
            if kwargs is None or not callable(attr):
                return attr
            return attr(**kwargs)
        except frappe.QueryDeadlockError:
            frappe.db.rollback()
            if attempt == attempts - 1:
                frappe.log_error(title="restaurant deadlock, out of retries",
                                 message="%s.%s on %s" % (model, method, name))
                raise
            frappe.local.message_log = []
            time.sleep(0.15 * (attempt + 1))


@frappe.whitelist()
def call(model, name, method, args=None):
    if args is not None:
        _args = json.loads(args)
        kwargs = {arg: _args[arg] for arg in _args}
        return _call_with_retry(model, name, method, kwargs)
    return _call_with_retry(model, name, method, None)'''

if OLD not in src:
    raise SystemExit("deadlock retry: api.call anchor not found")

open(P, "w").write(src.replace(OLD, NEW, 1))
print("deadlock retry: pad actions retry instead of surfacing a deadlock")
