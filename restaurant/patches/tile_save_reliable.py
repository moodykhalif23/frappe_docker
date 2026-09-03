# Two ways a resize or move was lost. Client: save_config() returned silently
# whenever any other save was in flight (window.saving), so a gesture that
# overlapped a dish or dialog save never reached the server — a hard refresh
# then showed the old size. Server: set_style broadcast the tile it had loaded
# BEFORE writing the new style, so every open floor snapped the tile back even
# when the save succeeded. Retry instead of dropping; reload before telling.
JS = "apps/restaurant_management/restaurant_management/public/restaurant/js/restaurant-object-class.js"
PY = "apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_object/restaurant_object.py"

js = open(JS).read()
if "rm_save_retry" in js:
    print("tile save: client already retries")
else:
    OLD = """  save_config(shape = false) {
    if (shape && this.data.type === 'Production Center') return;
    if (window.saving) return;
"""
    NEW = """  save_config(shape = false) {
    if (shape && this.data.type === 'Production Center') return;
    // rm_save_retry: another save in flight must delay this one, never drop it
    if (window.saving) {
      this._rm_save_tries = (this._rm_save_tries || 0) + 1;
      if (this._rm_save_tries > 40) { this._rm_save_tries = 0; window.saving = false; }
      clearTimeout(this._rm_save_retry);
      this._rm_save_retry = setTimeout(() => this.save_config(shape), 300);
      return;
    }
    this._rm_save_tries = 0;
"""
    if OLD not in js:
        raise SystemExit("tile save: save_config anchor not found")
    open(JS, "w").write(js.replace(OLD, NEW, 1))
    print("tile save: a resize or move waits for its turn instead of vanishing")

py = open(PY).read()
if "rm_style_fresh" in py:
    print("tile save: server already reloads before broadcasting")
else:
    OLD = """        frappe.db.set_value("Restaurant Object", self.name,
                            "shape" if shape else 'data_style', _data)
        self._on_update()
"""
    NEW = """        frappe.db.set_value("Restaurant Object", self.name,
                            "shape" if shape else 'data_style', _data)
        # rm_style_fresh: broadcast the style just written, not the one loaded
        self.reload()
        self._on_update()
"""
    if OLD not in py:
        raise SystemExit("tile save: set_style anchor not found")
    open(PY, "w").write(py.replace(OLD, NEW, 1))
    print("tile save: every floor sees the size that was saved")
