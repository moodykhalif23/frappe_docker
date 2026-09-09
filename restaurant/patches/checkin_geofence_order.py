# hrms demands coordinates before it checks whether any geofence applies, so a POS
# sign-in with no shift location assigned is refused for a rule that does not exist.
F = "apps/hrms/hrms/hr/doctype/employee_checkin/employee_checkin.py"
src = open(F).read()

if "rm_geofence_order" in src:
    print("checkin geofence: already applied")
    raise SystemExit

DEMAND = '''		if not (self.latitude or self.longitude):
			frappe.throw(_("Latitude and longitude values are required for checking in."))

'''
GATE = '''		if not assignment_locations:
			return

'''
if src.count(DEMAND) != 1 or src.count(GATE) != 1:
    raise SystemExit("checkin geofence: anchors not found exactly once")

# rm_geofence_order: ask for coordinates only once a shift location is known to apply
src = src.replace(DEMAND, "", 1)
src = src.replace(GATE, GATE.rstrip("\n") + "\n\n" + DEMAND, 1)
open(F, "w").write(src.replace(
    "	def validate_distance_from_shift_location(self):",
    "	# rm_geofence_order: coordinates are demanded only where a geofence exists\n"
    "	def validate_distance_from_shift_location(self):", 1))
print("checkin geofence: coordinates are asked for only where a geofence applies")
