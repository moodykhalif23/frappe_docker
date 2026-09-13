# Seating a walk-in demanded a typed guest name every single time, and
# RestaurantBooking._ensure_walkin_customer turns any unknown name into a real
# Customer — so the master filled with 'giest', 'guesat', 'gurst', 'f', '12',
# 'hj'. The house already has a walk-in account (POS Profile.customer =
# 'Walk-in Guest'); prefill it and accept a blank name. Idempotent.
RM = 'apps/restaurant_management/restaurant_management'

# --- 1. the seat dialog: prefill, and stop demanding a name ---
p1 = RM + '/restaurant_management/page/restaurant_manage/restaurant_manage.js'
s = open(p1).read()
if 'rm_walkin_default' in s:
    print('walkin_default: js already patched')
else:
    old = '{ fieldname: "guest_name", fieldtype: "Data", label: __("Guest name"), reqd: 1 },'
    assert s.count(old) == 1, 'seat dialog anchor %d' % s.count(old)
    new = ('{ fieldname: "guest_name", fieldtype: "Data", label: __("Guest name"), /* rm_walkin_default */\n'
           '            default: (window.RM && RM.pos_profile && RM.pos_profile.customer) || "Walk-in Guest",\n'
           '            description: __("Prefilled for walk-ins — type a name only if the party gives one") },')
    open(p1, 'w').write(s.replace(old, new, 1))
    print('walkin_default: seat dialog prefilled')

# --- 2. the server: a blank name means the house walk-in, not an error ---
p2 = RM + '/house.py'
h = open(p2).read()
if 'rm_walkin_default' in h:
    print('walkin_default: house.py already patched')
else:
    old2 = ('\tguest_name = (guest_name or "").strip()\n'
            '\tif not guest_name:\n'
            '\t\tfrappe.throw(frappe._("A guest name is required"))\n')
    assert h.count(old2) == 1, 'seat_walkin anchor %d' % h.count(old2)
    new2 = ('\tguest_name = (guest_name or "").strip()\n'
            '\tif not guest_name:\n'
            '\t\t# rm_walkin_default: a walk-in needs no name. Fall back to the house\n'
            '\t\t# walk-in account so seating is one tap and the Customer master stops\n'
            '\t\t# collecting a new record for every typo of "guest".\n'
            '\t\tguest_name = (frappe.db.get_value("POS Profile", {"disabled": 0}, "customer")\n'
            '\t\t\t\t\t  or "Walk-in Guest")\n')
    open(p2, 'w').write(h.replace(old2, new2, 1))
    print('walkin_default: seat_walkin accepts a blank name')
