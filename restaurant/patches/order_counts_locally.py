# The Order button decides whether there is anything to send from
# data.products_not_ordered — a count the SERVER computed when the check was
# last fetched. On a freshly opened pad that is 0 until the next realtime sync,
# so the button sits disabled and a double-click is a silent no-op. Seen on the
# live site after every seating; never locally, where the sync wins the race.
# Count the check's own lines instead.
ORDER = "apps/restaurant_management/restaurant_management/public/restaurant/js/table-order-class.js"
MANAGE = "apps/restaurant_management/restaurant_management/public/restaurant/js/order-manage-class.js"

osrc = open(ORDER).read()
if "get pending_count()" in osrc:
    print("order counts locally: check already counts itself")
else:
    OLD = """  order() {
    if (RM.busy_message() || this.data.products_not_ordered <= 0) {
      return;
    }"""
    NEW = """  // Lines added but not yet fired. Local state is current the instant a dish
  // lands; the server's products_not_ordered is not until the next sync.
  get pending_count() {
    const local = Object.values(this.items || {}).filter((i) =>
      i && i.data && flt(i.data.qty) > 0 && ["Pending", "Attending"].includes(i.data.status)).length;
    return Math.max(local, cint(this.data.products_not_ordered));
  }

  order() {
    if (RM.busy_message() || this.pending_count <= 0) {
      return;
    }"""
    if OLD not in osrc:
        raise SystemExit("order counts locally: order() anchor not found")
    open(ORDER, "w").write(osrc.replace(OLD, NEW, 1))
    print("order counts locally: Order fires when the check has unsent lines")

msrc = open(MANAGE).read()
OLD_M = "          const orders_count = this.current_order.data.products_not_ordered;"
NEW_M = "          const orders_count = this.current_order.pending_count;"
if NEW_M in msrc:
    print("order counts locally: badge already local")
elif OLD_M not in msrc:
    raise SystemExit("order counts locally: badge anchor not found")
else:
    open(MANAGE, "w").write(msrc.replace(OLD_M, NEW_M, 1))
    print("order counts locally: the Order badge enables as soon as a dish lands")
