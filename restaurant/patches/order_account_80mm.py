# The table bill / kitchen ticket printed ~213mm of 80mm roll for a 5-item
# order — the content itself is ~66mm. The stock "Order Account" format is
# ERPNext A4 boilerplate (line-height:150%, min-height:8in, width:4in,
# Bootstrap table padding, the letterhead with a 64px logo, three <hr> of
# which two are adjacent, and 2-3 text lines per item) and it carries no
# @page rule at all, so on a continuous roll the browser feeds a full page.
#
# Replace it with an 80mm-native template that owns all of its geometry,
# neutralises Frappe's letterhead/gutter/page-break machinery, prints one
# line per item, and can render a price-free kitchen copy (?kitchen=1).
#
# Order Account is a STANDARD format, so the html lives inside its .json;
# editing it in the UI would be lost on the next app update. Idempotent.
import json, os

MARK = "rm_order_80mm_v1"
JSON_PATH = "apps/restaurant_management/restaurant_management/restaurant_management/print_format/order_account/order_account.json"
HTML_PATH = "/tmp/order_account_80mm.html"

d = json.load(open(JSON_PATH))
if MARK in (d.get("html") or ""):
    print("order_account_80mm: already patched")
else:
    html = open(HTML_PATH).read()
    assert MARK in html, "new template is missing its marker"
    d["html"] = html
    d["font_size"] = 9          # stop Print Settings' site-wide 14 applying
    d["margin_top"] = 0
    d["margin_bottom"] = 0
    d["margin_left"] = 0
    d["margin_right"] = 0
    json.dump(d, open(JSON_PATH, "w"), indent=1, sort_keys=True)
    print("order_account_80mm: patched (%d bytes of html)" % len(html))
