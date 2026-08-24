# The pay form threw before it could render: make() -> set_values() -> set_value()
# -> set_total_payment() reads this.actions, which make() only creates afterwards.
# Checkout was impossible — "Cannot read properties of undefined (reading 'pay')".
P = "apps/restaurant_management/restaurant_management/public/restaurant/js/pay-form-class.js"

src = open(P).read()
OLD = """    if (this.actions.pay) {"""
NEW = """    if (this.actions && this.actions.pay) {"""

if NEW in src:
    print("pay form init: already guarded")
    raise SystemExit
if OLD not in src:
    raise SystemExit("pay form init: anchor not found")

open(P, "w").write(src.replace(OLD, NEW, 1))
print("pay form init: guarded this.actions")
