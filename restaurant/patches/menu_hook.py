# Saving a Restaurant Menu switches any joining dish that still has Maintain
# Stock on (the Item form's default) to non-stock, unless stock ever moved for
# it — with no quantity in the warehouse the till refused to sell such a dish.
P = "apps/restaurant_management/restaurant_management/hooks.py"
src = open(P).read()
if "rm_menu_hook" in src:
    print("menu hook: already applied")
    raise SystemExit
src = src.rstrip("\n") + '''

# rm_menu_hook: a dish that joins the menu is sold as a recipe, never from stock
doc_events = globals().get("doc_events") or {}
doc_events.setdefault("Restaurant Menu", {})["on_update"] = "restaurant_management.house.menu_sells_without_stock_hook"
'''
open(P, "w").write(src)
print("menu hook: Restaurant Menu.on_update -> menu_sells_without_stock")
