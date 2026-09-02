# Photo-first menu card: picture on top, the name, then the price at the left
# and a "- n +" pill at the right where n is what is already on the check.
# "+" stays the app's own add-item control (one tap adds one), "-" takes one off
# the check the way the cart's trash does, so no new server semantics appear.
P = "apps/restaurant_management/restaurant_management/public/restaurant/js/product-item-class.js"

src = open(P).read()
if "rm-cart-minus" in src:
    print("card layout: already applied")
    raise SystemExit

OLD_FOOTER = '''                        <div class="input-group-append items-in-cart" style="display:none; background-color:green; border-radius:50px;">
                            <span class="input-group-text fa fa-shopping-cart" style="background-color: transparent; border: none; color:white;">
                                <span class="qty-in-cart" style="padding-left:5px;">0</span>
                            </span>
                        </div>
                    </div>
                </div>
                <a class="btn btn-success add-item" data-action="add" style="float:right; border-radius:50px;">
                    <span class="sr-only">${__('Add')}</span>
                    ${__('Add')} ${price_list_rate}
                </a>
            </div>'''

NEW_FOOTER = '''                        <span class="rm-cart-minus" title="${__('Remove one')}">&minus;</span>
                        <div class="input-group-append items-in-cart" style="display:none; background-color:green; border-radius:50px;">
                            <span class="input-group-text fa fa-shopping-cart" style="background-color: transparent; border: none; color:white;">
                                <span class="qty-in-cart" style="padding-left:5px;">0</span>
                            </span>
                        </div>
                        <a class="btn btn-success add-item" data-action="add" title="${__('Add')}">
                            <span class="sr-only">${__('Add')} ${price_list_rate}</span>+
                        </a>
                    </div>
                </div>
                <span class="rm-price">${price_list_rate}</span>
            </div>'''

if OLD_FOOTER not in src:
    raise SystemExit("card layout: footer anchor not found")
src = src.replace(OLD_FOOTER, NEW_FOOTER, 1)

# The price now sits left of the pill: the footer's flex order puts it first.
OLD_BIND = '''      add_item.on('click', (e) => {
        e.stopPropagation();
        const qty = parseInt(add_qty.html());'''
NEW_BIND = '''      // "-" on the card takes one off this check, exactly as the cart's trash does.
      $(this).find('.rm-cart-minus').on('click', (e) => {
        e.stopPropagation();
        const order = self.order_manage && self.order_manage.current_order;
        if (!order) return;
        let line = null;
        order.in_items(it => {
          if (it.data.item_code === item_code && RM.allows_to_edit_item.includes(it.data.status)) line = it;
        });
        if (!line) return;
        if (line.data.qty > 1) {
          line.data.qty -= 1;
          line.update(true);
        } else {
          line.delete();
        }
      });

      add_item.on('click', (e) => {
        e.stopPropagation();
        const qty = parseInt(add_qty.html());'''
if OLD_BIND not in src:
    raise SystemExit("card layout: add-item bind anchor not found")
src = src.replace(OLD_BIND, NEW_BIND, 1)

# The plus turns teal once the dish is on the check.
OLD_UPD = '''      if (item && item.data.qty > 0) {
        item_in_cart.show();
        item_in_cart_qty.html(item.data.qty);
      } else {
        item_in_cart.hide();
        item_in_cart_qty.html(0);
      }'''
NEW_UPD = '''      $(this).toggleClass('rm-has-qty', !!(item && item.data.qty > 0));
      if (item && item.data.qty > 0) {
        item_in_cart.show();
        item_in_cart_qty.html(item.data.qty);
      } else {
        item_in_cart.hide();
        item_in_cart_qty.html(0);
      }'''
if OLD_UPD not in src:
    raise SystemExit("card layout: update_items anchor not found")
src = src.replace(OLD_UPD, NEW_UPD, 1)

open(P, "w").write(src)
print("card layout: photo first, price left, - n + pill right")
