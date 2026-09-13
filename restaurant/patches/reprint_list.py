# A Reprint button on every POS Invoice list row. The restaurant-manage menu
# only offers the recent 25; the list has search and date filters, which is
# where staff actually go to find a bill that failed to print. Idempotent.
RM = 'apps/restaurant_management/restaurant_management'

# 1. the list-view script (public/js is symlinked into /assets, so it is served)
open(RM + '/public/js/pos_invoice_list.js', 'w').write(open('/tmp/pos_invoice_list.js').read())
print('reprint_list: pos_invoice_list.js written')

# 2. register it via the doctype_list_js hook
p = RM + '/hooks.py'
s = open(p).read()
if 'rm_reprint_list_hook' in s:
    print('reprint_list: hook already present')
else:
    anchor = '# doctype_list_js = {{"doctype" : "public/js/doctype_list.js"}}'
    assert s.count(anchor) == 1, 'hook anchor %d' % s.count(anchor)
    s = s.replace(anchor, anchor + '\n\n# rm_reprint_list_hook: Reprint button on the POS Invoice list\n'
                  'doctype_list_js = {"POS Invoice": "public/js/pos_invoice_list.js"}', 1)
    open(p, 'w').write(s)
    import ast; ast.parse(s)
    print('reprint_list: doctype_list_js hook added')
