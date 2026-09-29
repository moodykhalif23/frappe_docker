# rm_receipt_80mm_auto — keep the receipt that was proven on the till's paper.
#
# The CITIZEN CT-S300 driver offers discrete media (80x3276 default, 80x297,
# 80x257...). Under Chrome --kiosk-printing a computed page height such as
# `80mm 59mm` has no matching media, so Chrome falls back to the 3.27 m default
# roll: the receipt printed at the top of metres of blank paper (21 Sep 2026).
# `size: 80mm auto` — what the bill and kitchen ticket use — sizes to the roll
# and cuts cleanly. The print head also reaches only ~72mm of the 80mm roll, so
# the right-hand amount column clipped; rm_printable_72mm keeps content inside.
#
# Both fixes went onto the live "Etham Receipt" record first. Without this
# patch, _ensure_receipt_format() copies the old template back over it on the
# next deploy (it re-pushes whenever the stored html differs). Only the two
# lines change, inside _COMPACT_RECEIPT alone, so other edits to the receipt in
# house.py still flow through.

P = 'apps/restaurant_management/restaurant_management/house.py'
GUARD = 'rm_receipt_80mm_auto'
HEAD = '_COMPACT_RECEIPT = """'
PAGE_OLD = '<style>@page { size: 80mm {{ 23 + (9 * _rows) // 2 }}mm; margin: 0 }</style>'
PAGE_NEW = '<style>@page { size: 80mm auto; margin: 0 }</style>'
W_ANCHOR = '  @media screen { .print-format { margin: 0 auto } }\n'
W_ADD = ('\n'
         '/* rm_printable_72mm: CT-S300 prints only ~72mm of the 80mm roll; keep all content inside the print head so the right-edge amount column cannot clip */\n'
         '.print-format{width:72mm !important;box-sizing:border-box !important;margin:0 !important;padding-left:2mm !important;padding-right:2mm !important}\n'
         '.rm-o table,.print-format table{width:100% !important}\n')

s = open(P).read()
if GUARD in s:
    print("receipt_80mm_auto: already present")
else:
    assert s.count(HEAD) == 1, "receipt literal seen %d times" % s.count(HEAD)
    start = s.index(HEAD) + len(HEAD)
    end = s.index('"""', start)
    body = s[start:end]
    assert body.count(PAGE_OLD) == 1, "computed @page seen %d times" % body.count(PAGE_OLD)
    assert body.count(W_ANCHOR) == 1, "width anchor seen %d times" % body.count(W_ANCHOR)
    assert "rm_printable_72mm" not in body
    body = body.replace(PAGE_OLD, PAGE_NEW, 1).replace(W_ANCHOR, W_ANCHOR + W_ADD, 1)
    lead = s[:s.index(HEAD)]
    s = (lead + "# rm_receipt_80mm_auto: page `80mm auto` + 72mm printable width, proven on the\n"
         "# till's CT-S300 (see restaurant/patches/receipt_80mm_auto.py)\n"
         + HEAD + body + s[end:])
    open(P, 'w').write(s)
    print("receipt_80mm_auto: patched")
