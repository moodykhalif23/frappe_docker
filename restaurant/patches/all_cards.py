# The pad's card list is virtualised in blocks of 40 rows, four blocks a cluster:
# 160 cards render and the rest hide behind a spacer sized for one card per row.
# With a four-column grid that spacer is a screenful of blank, and a 170-dish
# menu shows 160 until someone scrolls through it. Render every dish fetched at
# once, and fetch enough for a big menu: one number governs both. Categories
# and search refetch server-side, so a view never has to hold the whole menu.
P = "apps/restaurant_management/restaurant_management/public/restaurant/js/product-item-class.js"
LIMIT = 1000

src = open(P).read()
changed = []

# rows per block: every fetched dish renders in the first cluster
for old in ("      rows_in_block: 40,\n", "      rows_in_block: 400,   // rm_all_cards: every dish renders, no phantom spacer\n"):
    if old in src:
        src = src.replace(old, "      rows_in_block: %d,   // rm_all_cards: every dish fetched renders, no phantom spacer\n" % LIMIT, 1)
        changed.append("rows_in_block %d" % LIMIT)
if "rm_all_cards" not in src:
    raise SystemExit("all cards: rows_in_block anchor not found")

# the fetch cap: upstream stopped at 400 dishes per view
old = "get_items({ start = 0, page_length = 400, search_value"
if old in src:
    src = src.replace(old, "get_items({ start = 0, page_length = %d /* rm_all_cards_fetch */, search_value" % LIMIT, 1)
    changed.append("page_length %d" % LIMIT)
if "rm_all_cards_fetch" not in src:
    raise SystemExit("all cards: page_length anchor not found")

open(P, "w").write(src)
print("all cards: " + (", ".join(changed) if changed else "already applied"))
