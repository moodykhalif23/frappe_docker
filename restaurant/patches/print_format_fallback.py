# RM.pos_profile.print_format is optional, and when it is unset the pad asks the
# server to render "undefined" — the receipt dialog opens blank.
P = "apps/restaurant_management/restaurant_management/public/restaurant/js/pay-form-class.js"

src = open(P).read()
OLD = '''        format: RM.pos_profile.print_format,'''
NEW = '''        format: RM.pos_profile.print_format || "POS Invoice",'''

if NEW in src:
    print("print format: fallback already applied")
    raise SystemExit
if OLD not in src:
    raise SystemExit("print format: anchor not found in pay-form-class.js")

open(P, "w").write(src.replace(OLD, NEW, 1))
print("print format: falls back to POS Invoice")
