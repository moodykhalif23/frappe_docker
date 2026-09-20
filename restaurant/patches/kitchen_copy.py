RM = 'apps/restaurant_management/restaurant_management'
# --- pay-form-class.js: RM_print_ticket gains a kitchen flag ---
p1 = RM + '/public/restaurant/js/pay-form-class.js'
s = open(p1).read()
if 'params.set("kitchen"' not in s:
    a1 = 'window.RM_print_ticket = function (order_name) {'
    assert s.count(a1) == 1, 'sig anchor %d' % s.count(a1)
    s = s.replace(a1, 'window.RM_print_ticket = function (order_name, kitchen) {')
    a2 = ('    format: "Etham Order Bill",\n'
          '    no_letterhead: (window.RM && RM.pos_profile && RM.pos_profile.letter_head) ? 0 : 1,\n'
          '    trigger_print: 1,\n'
          '  });\n'
          '  if (window.RM && RM.lang) params.set("_lang", RM.lang);')
    b2 = ('    format: "Etham Order Bill",\n'
          '    no_letterhead: (window.RM && RM.pos_profile && RM.pos_profile.letter_head) ? 0 : 1,\n'
          '    trigger_print: 1,\n'
          '  });\n'
          '  if (kitchen) params.set("kitchen", "1");\n'
          '  if (window.RM && RM.lang) params.set("_lang", RM.lang);')
    assert s.count(a2) == 1, 'params anchor %d' % s.count(a2)
    s = s.replace(a2, b2)
    open(p1,'w').write(s)
    print('kitchen_copy: pay-form patched')
else:
    print('kitchen_copy: pay-form already patched')
# --- process-manage-class.js: board prints are the kitchen copy ---
p2 = RM + '/public/restaurant/js/process-manage-class.js'
t = open(p2).read()
# the guard stops at the kitchen flag on purpose: kot_rounds_js later adds a
# third argument, and a guard that cannot recognise its own widened output
# re-enters on the next bake and dies on a vanished anchor
if 'RM_print_ticket(data.order_name || data.name, true' not in t:
    c1 = 'if (this.group_items_by_order) return RM_print_ticket(data.order_name || data.name);'
    assert t.count(c1) == 1, 'board anchor %d' % t.count(c1)
    t = t.replace(c1, 'if (this.group_items_by_order) return RM_print_ticket(data.order_name || data.name, true);')
    c2 = '.then(({ message }) => message && RM_print_ticket(message));'
    assert t.count(c2) == 1, 'ticket_order anchor %d' % t.count(c2)
    t = t.replace(c2, '.then(({ message }) => message && RM_print_ticket(message, true));')
    open(p2,'w').write(t)
    print('kitchen_copy: process-manage patched')
else:
    print('kitchen_copy: process-manage already patched')
