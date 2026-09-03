# Rooms and tables are named by their description (clean_names.py). frappe's
# _sync_autoname_field() then resets that field to the docname on every save, so
# typing a new Description in "Update Table" was silently reverted while the
# seat count saved. A changed description is a rename request: do the rename.
P = ("apps/restaurant_management/restaurant_management/restaurant_management/"
     "doctype/restaurant_object/restaurant_object.py")

src = open(P).read()
if "rm_rename_on_description" in src:
    print("rename on description: already applied")
    raise SystemExit

ANCHOR = "    def after_delete(self):"
if src.count(ANCHOR) != 1:
    raise SystemExit("rename on description: after_delete anchor not found")

BLOCK = '''    # rm_rename_on_description: the description names the record, so changing
    # it renames the record — frappe would otherwise put the old name back.
    _RM_FORBIDDEN = re.compile(r'[<>;,"\\'#/\\\\%?]')

    def _rm_wanted_name(self):
        wanted = re.sub(r"\\s+", " ", self._RM_FORBIDDEN.sub("", self.description or "")).strip()
        if self.is_new() or not wanted or wanted == self.name:
            return None
        return wanted

    def save(self, *args, **kwargs):
        wanted = self._rm_wanted_name()
        if wanted is None:
            return super().save(*args, **kwargs)
        if frappe.db.exists("Restaurant Object", wanted):
            frappe.throw(_("There is already a {0} called {1}").format(_(self.type).lower(), wanted))
        # save the rest under the old name, then move the record
        self.description = self.name
        result = super().save(*args, **kwargs)
        old = self.name
        frappe.rename_doc("Restaurant Object", old, wanted, force=True, show_alert=False)
        frappe.db.set_value("Restaurant Object", wanted, "description", wanted, update_modified=False)
        # Link fields follow a rename; these columns are plain copies and do not.
        for table, column in (("tabOrder Entry Item", "room"), ("tabRestaurant Booking", "room"),
                              ("tabRestaurant Permission", "room")):
            if frappe.db.table_exists(table[3:]) and frappe.db.has_column(table[3:], column):
                frappe.db.sql("update `%s` set `%s`=%%s where `%s`=%%s" % (table, column, column), (wanted, old))
        self.name = wanted
        self.description = wanted
        # every open floor still listens on the old name: send it the renamed tile
        if self.type == "Room":
            payload = self.get_data()
        else:
            found = self.get_objects(wanted)["tables"]
            payload = found[0] if found else None
        frappe.publish_realtime(old, dict(action="Update", data=payload))
        return result

'''

src = src.replace(ANCHOR, BLOCK + ANCHOR, 1)
if "\nimport re\n" not in src:
    src = src.replace("import random\nimport string", "import random\nimport re\nimport string", 1)
open(P, "w").write(src)
print("rename on description: a new description renames the room or table")
