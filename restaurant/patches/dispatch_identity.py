# Firing an order to the kitchen went through api.call → TableOrder.send with no
# idea who was holding the tablet; the check's waiter was whoever seated it.
# Order now confirms the waiter's PIN (within the admin's grace window) and calls
# house.dispatch, which stamps every fired line with that waiter and leaves a
# timeline note — the seater owns the check, the firer owns the lines.
P = "apps/restaurant_management/restaurant_management/public/restaurant/js/table-order-class.js"

src = open(P).read()
if "rm_dispatch_identity" in src:
    print("dispatch identity: already applied")
    raise SystemExit

OLD = """    RM.working("Send order to Prepare");

    frappeHelper.api.call({
      model: "Table Order",
      name: this.data.name,
      method: "send",
      always: (r) => {
        this.order_manage.components.Order.remove_class("btn-warning");
        RM.ready(false, "success");
        this.data = r.message.order.data;
        this.render();
        this.check_items({ items: r.message.items });
      },
    });
  }"""
NEW = """    // rm_dispatch_identity: who is firing this? Ask (within the grace window,
    // remember), then send as that waiter so every line carries a name.
    const fire = (who) => {
      RM.working("Send order to Prepare");
      frappe.call({
        method: "restaurant_management.house.dispatch",
        args: { order: this.data.name, waiter: who.waiter, token: who.token },
      }).then((r) => {
        this.order_manage.components.Order.remove_class("btn-warning");
        RM.ready(false, "success");
        if (!r.message) return;
        this.data = r.message.order.data;
        this.render();
        this.check_items({ items: r.message.items });
      }).catch(() => RM.ready(false, "error"));
    };
    if (window.RM_waiter && RM_waiter.confirm) return RM_waiter.confirm("order").then(fire);
    // no waiter module on this page (a bare desk session): fire as the login
    fire({ waiter: null, token: null });
  }"""
if src.count(OLD) != 1:
    raise SystemExit("dispatch identity: order() body found %d times" % src.count(OLD))
open(P, "w").write(src.replace(OLD, NEW, 1))
print("dispatch identity: Order asks who is firing and records it per line")
