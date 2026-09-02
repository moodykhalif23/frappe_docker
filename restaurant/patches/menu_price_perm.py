# Item Price create is Sales Master Manager only, so a manager with Item Manager
# could rename a dish but never price a new one. The fence is Item write above.
P = "apps/restaurant_management/restaurant_management/api.py"
src = open(P).read()

OLD = '''                    "price_list_rate": flt(rate), "selling": 1,
                }).insert()'''
NEW = '''                    "price_list_rate": flt(rate), "selling": 1,
                }).insert(ignore_permissions=True)'''

if NEW in src:
    print("menu price perm: already applied")
elif OLD not in src:
    raise SystemExit("menu price perm: Item Price insert anchor not found")
else:
    open(P, "w").write(src.replace(OLD, NEW, 1))
    print("menu price perm: a manager can price a new dish")
