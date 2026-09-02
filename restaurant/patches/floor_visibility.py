# Restaurant Permissions are opt-in and nobody fills them in, but every
# non-manager is filtered *through* them: rooms, tables, order counts and
# can_access() all treat the empty list as "you may see nothing". A waiter
# tablet holding only Restaurant User therefore shows a floor with no rooms at
# all — which is what happened the moment Restaurant Manager was taken off the
# station accounts so they could not delete tables.
P = ("apps/restaurant_management/restaurant_management/restaurant_management/"
     "doctype/restaurant_settings/restaurant_settings.py")

src = open(P).read()
if "rm_unconfigured_means_unrestricted" in src:
    print("floor visibility: already applied")
    raise SystemExit

OLD = """    def restaurant_access(self, type="Room", more_filters=None):
        pos_profile_name = self.get_current_pos_profile_name()
"""

NEW = """    def restaurant_access(self, type="Room", more_filters=None):
        # rm_unconfigured_means_unrestricted: with no Restaurant Permission rows
        # on the site the feature is simply unused, so the whole floor is open.
        if getattr(frappe.local, "rm_permission_rows", None) is None:
            # called once per table per repaint, so the count is memoized
            frappe.local.rm_permission_rows = frappe.db.count("Restaurant Permission")
        if not frappe.local.rm_permission_rows:
            if more_filters and more_filters.get("is_crm"):
                return set()
            object_filters = {"type": "Room"} if type == "Room" else {"type": ("!=", "Room")}
            names = set(frappe.get_all("Restaurant Object", filters=object_filters, pluck="name"))
            wanted = more_filters and more_filters.get("object_name")
            return (names & {wanted}) if wanted else names

        pos_profile_name = self.get_current_pos_profile_name()
"""

if OLD not in src:
    raise SystemExit("floor visibility: restaurant_access anchor not found")

open(P, "w").write(src.replace(OLD, NEW, 1))
print("floor visibility: a station with no permission rows sees the whole floor")
