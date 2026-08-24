# The pay form made the covers count mandatory for dine-in, so Pay stayed
# disabled until someone typed a number. A guest settling up should never be
# blocked by a statistic. The field stays visible and still records covers —
# it just defaults to 1 instead of holding the payment hostage.
P = "apps/restaurant_management/restaurant_management/public/restaurant/js/pay-form-class.js"

src = open(P).read()
OLD = """        this.set_field_property(["delivery_date", "pick_time", "branch", "address"], "reqd", 0);
        this.set_field_property("dinners", "reqd", 1);
        this.get_field("dinners").$wrapper.show();"""
NEW = """        this.set_field_property(["delivery_date", "pick_time", "branch", "address"], "reqd", 0);
        this.set_field_property("dinners", "reqd", 0);
        this.get_field("dinners").$wrapper.show();
        if (!this.get_value("dinners")) this.set_value("dinners", 1);"""

if 'this.set_field_property("dinners", "reqd", 0);\n        this.get_field("dinners").$wrapper.show();' in src:
    print("dinners: already optional")
    raise SystemExit
if OLD not in src:
    raise SystemExit("dinners: anchor not found")

open(P, "w").write(src.replace(OLD, NEW, 1))
print("dinners: optional, defaults to 1")
