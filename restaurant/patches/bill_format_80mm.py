# rm_order_bill_sync — "Etham Order Bill" is the format the POS actually prints
# (RM_print_ticket hardcodes the name). It is a DB record, not a file, so it has
# to be kept in step with the 80mm template that lives on the Order Account
# format. The previous version only re-copied when a version marker was absent
# from the stored html, which meant editing the template without remembering to
# bump that marker left the printed bill silently one build behind. Comparing
# the html itself cannot go stale.
import re

p = 'apps/restaurant_management/restaurant_management/house.py'
s = open(p).read()
if 'rm_order_bill_sync' in s:
    print('bill_format_80mm: already patched'); raise SystemExit(0)

new_fn = '''def _ensure_bill_format():
\t"""rm_order_bill_sync: waiter bill / kitchen ticket.

\tUses the 80mm template kept on the Order Account format VERBATIM — one source
\tof truth — and re-copies it whenever the two differ. The template self-selects
\ta price-free kitchen copy when the URL carries kitchen=1, and one fired round
\twhen it carries kot_round=N."""
\tname = "Etham Order Bill"
\tbase = frappe.db.get_value("Print Format", "Order Account", "html")
\tif not base:
\t\treturn None
\tif frappe.db.exists("Print Format", name):
\t\tcurrent = frappe.db.get_value("Print Format", name, "html") or ""
\t\tif current != base:
\t\t\tfrappe.db.set_value("Print Format", name, "html", base, update_modified=False)
\t\tfrappe.db.set_value("Print Format", name, {"custom_format": 1, "font_size": 9,
\t\t\t\t\t\t\t"pdf_generator": "wkhtmltopdf", "disabled": 0}, update_modified=False)
\t\treturn name
\tfrappe.get_doc({
\t\t"doctype": "Print Format", "name": name, "doc_type": "Table Order",
\t\t"module": "Restaurant Management", "print_format_type": "Jinja", "standard": "No",
\t\t"pdf_generator": "wkhtmltopdf", "disabled": 0, "font_size": 9, "custom_format": 1,
\t\t"html": base,
\t}).insert(ignore_permissions=True)
\treturn name
'''

s2 = re.sub(r'def _ensure_bill_format\(\):.*?(?=\ndef ensure_custom_fields\()', new_fn, s,
            count=1, flags=re.S)
assert s2 != s, 'anchor not matched'
assert 'rm_order_bill_sync' in s2
open(p, 'w').write(s2)
import ast; ast.parse(s2)
print('bill_format_80mm: patched')
