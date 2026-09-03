# In edit mode a drag on an UNSELECTED tile did nothing: initDrag bailed out,
# the mouse-up then selected the tile, and only a second drag moved or resized
# it. Because a click on a selected tile deselects it again, the floor editor
# felt like it "worked once and then stopped". A drag now selects as it starts.
P = "apps/restaurant_management/restaurant_management/public/restaurant/js/restaurant-object-class.js"

src = open(P).read()
if "rm_drag_selects" in src:
    print("drag selects: already applied")
    raise SystemExit

OLD = """    const initDrag = () => {
      if (!this.is_selected) return;
      self.drag = true;
      self.obj.add_class("drag");
    }"""
NEW = """    const initDrag = () => {
      // rm_drag_selects: the gesture itself selects the tile, no prior click needed
      if (!this.is_selected) {
        if (!RM.editing) return;
        this.obj.add_class("selected").JQ().siblings(".d-table.selected").removeClass("selected");
      }
      self.drag = true;
      self.obj.add_class("drag");
    }"""
if src.count(OLD) != 1:
    raise SystemExit("drag selects: initDrag anchor not found")
open(P, "w").write(src.replace(OLD, NEW, 1))
print("drag selects: a drag selects the tile as it starts")
