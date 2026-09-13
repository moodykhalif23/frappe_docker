import re
p = 'apps/restaurant_management/restaurant_management/house.py'
s = open(p).read()
if 'rm_order_80mm_v1 bill' in s:
    print('bill_format_80mm: already patched'); raise SystemExit(0)
new_fn = (
'def _ensure_bill_format():\n'
'\t"""rm_order_80mm_v1 bill: waiter bill / kitchen ticket. Use the 80mm\n'
'\ttemplate kept on the Order Account format verbatim (one source of truth);\n'
'\tit self-selects a price-free kitchen copy when the URL carries kitchen=1."""\n'
'\tname = "Etham Order Bill"\n'
'\tbase = frappe.db.get_value("Print Format", "Order Account", "html")\n'
'\tif not base:\n'
'\t\treturn None\n'
'\tmark = "rm_order_80mm_v1"\n'
'\tif frappe.db.exists("Print Format", name):\n'
'\t\tcurrent = frappe.db.get_value("Print Format", name, "html") or ""\n'
'\t\tif mark not in current:\n'
'\t\t\tfrappe.db.set_value("Print Format", name, "html", base, update_modified=False)\n'
'\t\tfrappe.db.set_value("Print Format", name, {"custom_format": 1, "font_size": 9,\n'
'\t\t\t\t\t\t\t"pdf_generator": "wkhtmltopdf", "disabled": 0}, update_modified=False)\n'
'\t\treturn name\n'
'\tfrappe.get_doc({\n'
'\t\t"doctype": "Print Format", "name": name, "doc_type": "Table Order",\n'
'\t\t"module": "Restaurant Management", "print_format_type": "Jinja", "standard": "No",\n'
'\t\t"pdf_generator": "wkhtmltopdf", "disabled": 0, "font_size": 9, "custom_format": 1,\n'
'\t\t"html": base,\n'
'\t}).insert(ignore_permissions=True)\n'
'\treturn name\n'
)
s2 = re.sub(r'def _ensure_bill_format\(\):.*?(?=\ndef ensure_custom_fields\()', new_fn, s, count=1, flags=re.S)
assert s2 != s, 'anchor not matched'
open(p,'w').write(s2)
import ast; ast.parse(s2)
print('bill_format_80mm: patched')
