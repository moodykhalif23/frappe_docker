# Tables are named after their description now ("Table 1"), and the pad builds DOM
# ids from that name — jQuery reads $("#items-container-Table 1") as two selectors.
import re

FILES = {
    "apps/restaurant_management/restaurant_management/public/restaurant/js/order-manage-class.js": [
        ('wrapper: $(`#${this.item_container_name}`),',
         'wrapper: $(document.getElementById(this.item_container_name)),'),
        ('$("#" + this.pad_container_name).empty()',
         '$(document.getElementById(this.pad_container_name)).empty()'),
        ('const container = $("#" + this.identifier);',
         'const container = $(document.getElementById(this.identifier));'),
    ],
    "apps/restaurant_management/restaurant_management/public/restaurant/js/menu-manage-class.js": [
        ('wrapper: $(`#${this.item_container_name}`),',
         'wrapper: $(document.getElementById(this.item_container_name)),'),
    ],
    "apps/restaurant_management/restaurant_management/public/restaurant/js/process-manage-class.js": [
        ('return $(`#orders-${this.table.data.name}`);',
         'return $(document.getElementById(`orders-${this.table.data.name}`));'),
    ],
}

changed = 0
for path, pairs in FILES.items():
    src = open(path).read()
    before = src
    for old, new in pairs:
        if new in src:
            continue
        if old not in src:
            raise SystemExit("id selector: anchor not found in %s -> %s" % (path, old[:50]))
        src = src.replace(old, new, 1)
    if src != before:
        open(path, "w").write(src)
        changed += 1

print("id selector: %d file(s) look ids up by element, spaces and all" % changed
      if changed else "id selector: already applied")
