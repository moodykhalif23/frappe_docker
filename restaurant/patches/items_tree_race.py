# The pad's menu opens itself from a setTimeout, but the icon and the items
# container each resolve on their own timer — lose that race and the menu is
# empty: the icon throws, or Clusterize fails with "Could not find scroll element".
P = "apps/restaurant_management/restaurant_management/public/restaurant/js/items-tree-class.js"

src = open(P).read()
if "open_when_ready" in src:
    print("items tree: menu already waits for its DOM")
    raise SystemExit

ICON_OLD = '''        icon.obj.setAttribute("href"'''
ICON_NEW = '''        icon.obj && icon.obj.setAttribute("href"'''
if ICON_OLD in src:
    src = src.replace(ICON_OLD, ICON_NEW, 1)

OLD = '''      this.update_items_count();
      setTimeout(() => {
        item.name === "All Item Groups" && open_children();
        //opened && open_children();
      }, 0);'''
NEW = '''      this.update_items_count();

      const open_when_ready = (tries = 0) => {
        const ready = icon.obj && wrapper.find(`[area-items="${item.name}"]`).length;
        if (!ready) return tries < 60 && setTimeout(() => open_when_ready(tries + 1), 50);
        open_children();
      };

      setTimeout(() => {
        item.name === "All Item Groups" && open_when_ready();
      }, 0);'''

if OLD not in src:
    raise SystemExit("items tree: auto-open anchor not found")

open(P, "w").write(src.replace(OLD, NEW, 1))
print("items tree: menu waits for its DOM before opening")
