# The receipt never printed after payment: line 30 of the Etham Receipt template
# did {{ doc.posting_time[:5] }}, but frappe returns a Time field as a
# datetime.timedelta, which is not subscriptable -> PrintFormatError on every
# render -> the hidden print frame loaded an error page and nothing came out.
# Payment still recorded, so it failed silently.
#
# format_time(..., 'HH:mm') is also zero-padded: a 09:05 breakfast sale rendered
# '9:05:' through the old string-slice. Bump the build marker so
# _ensure_receipt_format() refreshes the live record. Idempotent.
p = 'apps/restaurant_management/restaurant_management/house.py'
s = open(p).read()
if 'format_time(doc.posting_time' in s:
    print('receipt_time_fix: already patched'); raise SystemExit(0)
old = '{{ doc.posting_time[:5] }}'
assert s.count(old) == 1, 'anchor count=%d' % s.count(old)
s = s.replace(old, '{{ frappe.utils.format_time(doc.posting_time, "HH:mm") }}')
n = s.count('rm_receipt_v2')
s = s.replace('rm_receipt_v2', 'rm_receipt_v3')
open(p, 'w').write(s)
import ast; ast.parse(s)
print('receipt_time_fix: patched (%d build markers bumped)' % n)
