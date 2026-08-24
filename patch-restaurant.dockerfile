FROM custom-erpnext:v16.32.3
USER frappe
# Refuse to build on an app version we have not reviewed. Our patches anchor on
# exact upstream source, and the restaurant app tracks a tagless master.
COPY restaurant/PINNED_APPS /tmp/PINNED_APPS
COPY restaurant/patches/assert_pins.py /tmp/assert_pins.py
RUN python3 /tmp/assert_pins.py

RUN sed -i "s/Sales Taxes And Charges/Sales Taxes and Charges/; s/tax += item.tax_amount$/tax += (item.tax_amount or 0)/; s/amount += item.amount$/amount += (item.amount or 0)/; s/\"rate\", \"amount\"/\"rate\", \"tax_amount\"/; s/tax\.amount or 0/tax.tax_amount or 0/" apps/restaurant_management/restaurant_management/restaurant_management/doctype/table_order/table_order.py
RUN sed -i "s/ RM = new RestaurantManage(wrapper);/ RM = window.RM = new RestaurantManage(wrapper);/" apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js
RUN sed -i 's/single_column: true$/single_column: true,\n    hide_sidebar: true/' apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js \
 ; sed -i 's|self.close_pos();|window.location.href = "/app";|g' apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js \
 && node --check apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js
# v16 page-closure trap (same as window.RM): the class asset files read these constants globally
RUN grep -q 'Object.assign(window, { TRANSFER' apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js \
 || sed -i 's/^const \[TRANSFER/Object.assign(window, { TRANSFER: "Transfer", UPDATE: "Update", DELETE: "Delete", INVOICED: "Invoiced", ADD: "Add", QUEUE: "queue", SPLIT: "Split", DOUBLE_CLICK_DELAY: "double_click" });\nconst [TRANSFER/' apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js \
 && node --check apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js
# make_reservation() fires before template() creates reservation_wrapper — guard it (TypeError: reading 'JQ')
RUN grep -q 'this.reservation_wrapper && Reservation.render' apps/restaurant_management/restaurant_management/public/restaurant/js/order-manage-class.js \
 || sed -i 's|Reservation.render(this.table.data.name, this.reservation_wrapper.JQ());|this.reservation_wrapper \&\& Reservation.render(this.table.data.name, this.reservation_wrapper.JQ());|' apps/restaurant_management/restaurant_management/public/restaurant/js/order-manage-class.js \
 && node --check apps/restaurant_management/restaurant_management/public/restaurant/js/order-manage-class.js
# order header: unguarded ${this.table.data.customer} renders "null" when no customer is checked in
RUN sed -i 's|${this.table.data.description}) ${this.table.data.customer}`|${this.table.data.description}) ${this.table.data.customer \|\| ""}`|' apps/restaurant_management/restaurant_management/public/restaurant/js/order-manage-class.js \
 && node --check apps/restaurant_management/restaurant_management/public/restaurant/js/order-manage-class.js
# v16 renamed get_item_details' kwarg args->ctx — without this every add-to-cart 500s and the cart stays empty
RUN grep -q 'args: { ctx: item }' apps/restaurant_management/restaurant_management/public/restaurant/js/product-item-class.js \
 || sed -i 's|args: { args: item }|args: { ctx: item }|' apps/restaurant_management/restaurant_management/public/restaurant/js/product-item-class.js \
 && node --check apps/restaurant_management/restaurant_management/public/restaurant/js/product-item-class.js
# food cards: item.description is often null — don't render the literal "null"
RUN sed -i 's/\${description}/\${description || ""}/' apps/restaurant_management/restaurant_management/public/restaurant/js/menu-manage-class.js apps/restaurant_management/restaurant_management/public/restaurant/js/product-item-class.js \
 && node --check apps/restaurant_management/restaurant_management/public/restaurant/js/menu-manage-class.js \
 && node --check apps/restaurant_management/restaurant_management/public/restaurant/js/product-item-class.js
# food cards inherit frappe's desk-shortcut hover (dark border) — neutralize it
COPY restaurant/patches/restaurant_manage_css_append.css /tmp/rm_css_append.css
RUN grep -q 'rm-no-card-hover' apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.css \
 || cat /tmp/rm_css_append.css >> apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.css
# restaurant-kit features: guest order tracker + in-POS menu item editor (writes stay on frappe doctypes)
COPY restaurant/patches/api_append.py /tmp/api_append.py
RUN grep -q 'def upsert_menu_item' apps/restaurant_management/restaurant_management/api.py \
 || cat /tmp/api_append.py >> apps/restaurant_management/restaurant_management/api.py \
 && python3 -c "import ast; ast.parse(open('apps/restaurant_management/restaurant_management/api.py').read())"
COPY restaurant/patches/order-status.html apps/restaurant_management/restaurant_management/public/order-status.html
COPY restaurant/patches/menu-item-editor.js apps/restaurant_management/restaurant_management/public/restaurant/js/menu-item-editor.js
RUN grep -q 'menu-item-editor.js' apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js \
 || sed -i "s|'js/items-tree-class.js',|'js/items-tree-class.js',\n      'js/menu-item-editor.js',|" apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js \
 && node --check apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js \
 && node --check apps/restaurant_management/restaurant_management/public/restaurant/js/menu-item-editor.js
COPY restaurant/patches/restaurant_booking_append.py /tmp/rb_append.py
RUN sed -i '/^\tdef before_insert/,/self.customer = customer.name$/d' apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_booking/restaurant_booking.py \
 ; grep -q "_ensure_walkin_customer" apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_booking/restaurant_booking.py \
 || cat /tmp/rb_append.py >> apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_booking/restaurant_booking.py \
 ; sed -i '/set_value("Customer", self.name, "mobile_no"/s/self.name/self.customer/' apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_booking/restaurant_booking.py \
 && python3 -c "import ast; ast.parse(open('apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_booking/restaurant_booking.py').read())"
RUN python3 - <<'PY'
# Undo the asset-url stamping baked into earlier images: it broke frappe's loader.
path = "apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js"
src = open(path).read()
bad = '${asset}?v=${window.RM_BUILD || "0"}'
if bad in src:
    open(path, "w").write(src.replace(bad, "${asset}"))
    print("reverted asset url stamping")
PY

# Our appended blocks are stripped before being re-appended: a grep guard would
# skip the append after we edit a block, silently serving the old version forever.
RUN python3 - <<'PY'
for path, marker in (
    ("apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js", "\n// One house shift: erpnext bills"),
    ("apps/restaurant_management/restaurant_management/restaurant_management/doctype/table_order/table_order.py", "\n    def _stamp_waiter("),
    ("apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.css", "\n/* rm-waiter-badge"),
):
    body = open(path).read()
    cut = body.find(marker)
    if cut != -1:
        open(path, "w").write(body[:cut].rstrip() + "\n")
        print("reset " + path)
PY

# one house shift: erpnext bills against the newest open POS Opening Entry per profile,
# so the stock per-user lookup stranded every waiter who did not open the shift
COPY --chown=frappe:frappe restaurant/patches/house.py apps/restaurant_management/restaurant_management/house.py
COPY restaurant/patches/house_shift_override.js /tmp/house_shift_override.js
RUN { echo ';'; cat /tmp/house_shift_override.js; } >> apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js && node --check apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js \
 && python3 -c "import ast; ast.parse(open('apps/restaurant_management/restaurant_management/house.py').read())"

RUN grep -q 'RM_house_shift(this.pos' apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js \
 || sed -i 's|window.cur_pos = this.pos;|window.cur_pos = this.pos;\n          this.pos.check_opening_entry = (p) => RM_house_shift(this.pos, p);|' apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js \
 && node --check apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js

# host stand: seat a walk-in by name onto a table that fits, then straight to the pad
COPY restaurant/patches/host_stand.js /tmp/host_stand.js
RUN { echo ';'; cat /tmp/host_stand.js; } >> apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js && node --check apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js
RUN grep -q 'RM_host_stand.mount(this)' apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js \
 || sed -i "s|() => this.page.set_title(__('Restaurant Manage')),|() => { this.page.set_title(__('Restaurant Manage')); window.RM_host_stand \&\& RM_host_stand.mount(this); },|" apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js \
 && node --check apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js

# waiter attribution: a Restaurant Waiter record with a PIN, stamped down the chain
COPY --chown=frappe:frappe restaurant/patches/doctype/restaurant_waiter apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_waiter
COPY restaurant/patches/table_order_waiter.py /tmp/table_order_waiter.py
RUN grep -q 'to_doc.waiter' apps/restaurant_management/restaurant_management/restaurant_management/doctype/table_order/table_order.py \
 || sed -i 's|        to_doc.table = self.table|        to_doc.table = self.table\n        to_doc.waiter = self.get("waiter")|' apps/restaurant_management/restaurant_management/restaurant_management/doctype/table_order/table_order.py
RUN cat /tmp/table_order_waiter.py >> apps/restaurant_management/restaurant_management/restaurant_management/doctype/table_order/table_order.py && python3 -c "import ast; ast.parse(open('apps/restaurant_management/restaurant_management/restaurant_management/doctype/table_order/table_order.py').read())"

# the floor needs to know who holds each table, and say so on the tile
RUN grep -q 'customer,waiter' apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_object/restaurant_object.py \
 || sed -i 's|,restricted_to_branches,customer"|,restricted_to_branches,customer,waiter"|' apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_object/restaurant_object.py \
 && python3 -c "import ast; ast.parse(open('apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_object/restaurant_object.py').read())"
RUN grep -q 'RM_waiter_badge(this.data.waiter)' apps/restaurant_management/restaurant_management/public/restaurant/js/restaurant-object-class.js \
 || sed -i 's|            \${this.description.html()}|            \${this.description.html()}\n            \${window.RM_waiter_badge ? RM_waiter_badge(this.data.waiter) : ""}|' apps/restaurant_management/restaurant_management/public/restaurant/js/restaurant-object-class.js \
 && node --check apps/restaurant_management/restaurant_management/public/restaurant/js/restaurant-object-class.js
COPY restaurant/patches/door.js /tmp/door.js
COPY restaurant/patches/waiter_pad.js /tmp/waiter_pad.js
RUN { echo ';'; cat /tmp/door.js; } >> apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js && node --check apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js
RUN { echo ';'; cat /tmp/waiter_pad.js; } >> apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js && node --check apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js
RUN grep -q 'RM_waiter.mount(this)' apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js \
 || sed -i 's|RM_host_stand.mount(this);|RM_host_stand.mount(this); window.RM_waiter \&\& RM_waiter.mount(this); window.RM_door \&\& RM_door.mount(this);|' apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js \
 && node --check apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js
COPY restaurant/patches/waiter_badge.css /tmp/waiter_badge.css
COPY restaurant/patches/responsive.css /tmp/responsive.css
COPY restaurant/patches/menu_card.css /tmp/menu_card.css
COPY restaurant/patches/door.css /tmp/door.css
RUN cat /tmp/waiter_badge.css /tmp/responsive.css /tmp/menu_card.css /tmp/door.css >> apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.css
COPY --chown=frappe:frappe restaurant/patches/report/sales_by_waiter apps/restaurant_management/restaurant_management/restaurant_management/report/sales_by_waiter

# Build id, for telling at a glance which bake a browser is running. Do NOT append
# it to asset URLs: frappe's assets.extn() reads the extension from after the "?",
# so x.js?v=1 has no handler and the floor never loads. frappe.require already
# appends its own version to every asset it fetches.
COPY restaurant/patches/build_stamp.js /tmp/build_stamp.js
RUN { echo ';'; cat /tmp/build_stamp.js; } >> apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js \
 && sed -i "s|__RM_BUILD__|$(date -u +%Y%m%d%H%M%S)|" apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js \
 && node --check apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js

# tapping a dish with no open check was a silent no-op; make it open the check
COPY restaurant/patches/autostart_order.py /tmp/autostart_order.py
RUN python3 /tmp/autostart_order.py && node --check apps/restaurant_management/restaurant_management/public/restaurant/js/product-item-class.js

# a real-sized menu 400'd the items panel: the group list was one entry per dish
COPY restaurant/patches/dedupe_item_groups.py /tmp/dedupe_item_groups.py
RUN python3 /tmp/dedupe_item_groups.py && python3 -c "import ast; ast.parse(open('apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_settings/restaurant_settings.py').read())"

# deleting a table silently failed: _delete was a @property, so dispatch called None
COPY restaurant/patches/fix_table_delete.py /tmp/fix_table_delete.py
RUN python3 /tmp/fix_table_delete.py \
 && python3 -c "import ast; ast.parse(open('apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_object/restaurant_object.py').read())" \
 && node --check apps/restaurant_management/restaurant_management/public/restaurant/js/restaurant-object-class.js

# the table trash was bound to a double-click and gave no feedback on a single tap
COPY restaurant/patches/table_delete_single_click.py /tmp/table_delete_single_click.py
RUN python3 /tmp/table_delete_single_click.py && node --check apps/restaurant_management/restaurant_management/public/restaurant/js/restaurant-object-class.js

# the pay form read this.actions before make() created it, so checkout threw
COPY restaurant/patches/fix_pay_form_init.py /tmp/fix_pay_form_init.py
RUN python3 /tmp/fix_pay_form_init.py && node --check apps/restaurant_management/restaurant_management/public/restaurant/js/pay-form-class.js

# covers was mandatory on the pay form and blocked payment; default it instead
COPY restaurant/patches/dinners_not_mandatory.py /tmp/dinners_not_mandatory.py
RUN python3 /tmp/dinners_not_mandatory.py && node --check apps/restaurant_management/restaurant_management/public/restaurant/js/pay-form-class.js

# Table turns: how many parties a table served and how long each sat
COPY --chown=frappe:frappe restaurant/patches/report/table_turns apps/restaurant_management/restaurant_management/restaurant_management/report/table_turns

# paying the check closes the booking, which frees the table and stamps the turn
COPY restaurant/patches/free_table_on_payment.py /tmp/free_table_on_payment.py
RUN python3 /tmp/free_table_on_payment.py \
 && python3 -c "import ast; ast.parse(open('apps/restaurant_management/restaurant_management/restaurant_management/doctype/table_order/table_order.py').read())"

# deleting a table: say what is holding it, and offer to clear an unpaid check
COPY restaurant/patches/table_delete_explains.py /tmp/table_delete_explains.py
RUN python3 /tmp/table_delete_explains.py \
 && node --check apps/restaurant_management/restaurant_management/public/restaurant/js/restaurant-object-class.js

# the reports and the waiter list had no way in but search
COPY restaurant/patches/workspace_reports.py /tmp/workspace_reports.py
RUN python3 /tmp/workspace_reports.py \
 && python3 -c "import json; json.load(open('apps/restaurant_management/restaurant_management/restaurant_management/workspace/restaurant/restaurant.json'))"
