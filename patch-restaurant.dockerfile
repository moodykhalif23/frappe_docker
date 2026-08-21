FROM custom-erpnext:v16.6.0
USER frappe
RUN sed -i "s/Sales Taxes And Charges/Sales Taxes and Charges/; s/tax += item.tax_amount$/tax += (item.tax_amount or 0)/; s/amount += item.amount$/amount += (item.amount or 0)/; s/\"rate\", \"amount\"/\"rate\", \"tax_amount\"/; s/tax\.amount or 0/tax.tax_amount or 0/" apps/restaurant_management/restaurant_management/restaurant_management/doctype/table_order/table_order.py
RUN sed -i "s/ RM = new RestaurantManage(wrapper);/ RM = window.RM = new RestaurantManage(wrapper);/" apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js
RUN sed -i 's/single_column: true$/single_column: true,\n    hide_sidebar: true/' apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js \
 ; sed -i 's|self.close_pos();|window.location.href = "/app";|g' apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js \
 && node --check apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js
# v16 page-closure trap (same as window.RM): the class asset files read these constants globally
RUN grep -q 'Object.assign(window, { TRANSFER' apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js \
 || sed -i 's/^const \[TRANSFER/Object.assign(window, { TRANSFER: "Transfer", UPDATE: "Update", DELETE: "Delete", INVOICED: "Invoiced", ADD: "Add", QUEUE: "queue", SPLIT: "Split", DOUBLE_CLICK_DELAY: "double_click" });\nconst [TRANSFER/' apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js \
 && node --check apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js
COPY restaurant/patches/restaurant_booking_append.py /tmp/rb_append.py
RUN sed -i '/^\tdef before_insert/,/self.customer = customer.name$/d' apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_booking/restaurant_booking.py \
 ; grep -q "_ensure_walkin_customer" apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_booking/restaurant_booking.py \
 || cat /tmp/rb_append.py >> apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_booking/restaurant_booking.py \
 ; sed -i '/set_value("Customer", self.name, "mobile_no"/s/self.name/self.customer/' apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_booking/restaurant_booking.py \
 && python3 -c "import ast; ast.parse(open('apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_booking/restaurant_booking.py').read())"
