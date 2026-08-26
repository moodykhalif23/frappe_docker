# Rooms and tables were named by random hash ("ocmhhmuk15"), with the readable
# label hidden in `description` — which the doctype already declares unique.
import json

DT = "apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_object/restaurant_object.json"
PAGE = "apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.py"
OBJ = "apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_object/restaurant_object.py"

doc = json.load(open(DT))
if doc.get("autoname") == "field:description":
    print("clean names: doctype already named by description")
else:
    doc["autoname"] = "field:description"
    doc["naming_rule"] = "By fieldname"
    json.dump(doc, open(DT, "w"), indent=1, sort_keys=True)
    print("clean names: Restaurant Object named by description")

src = open(PAGE).read()
OLD_ROOM = '''        room.description = f"R {(RestaurantManage().count_roms() + 1)}"'''
NEW_ROOM = '''        # description is unique and now names the record, so it has to be free.
        n = RestaurantManage().count_roms() + 1
        while frappe.db.exists("Restaurant Object", {"description": f"R {n}"}):
            n += 1
        room.description = f"R {n}"'''
if NEW_ROOM in src:
    print("clean names: add_room already picks a free name")
elif OLD_ROOM in src:
    open(PAGE, "w").write(src.replace(OLD_ROOM, NEW_ROOM, 1))
    print("clean names: add_room picks a free name")
else:
    raise SystemExit("clean names: add_room anchor not found")

src = open(OBJ).read()
OLD_TABLE = '''        name = f"{t[:1]}-{random.randint(random.randint(1, 100), random.randint(100, 1000))}"'''
NEW_TABLE = '''        name = f"{t[:1]}-{random.randint(random.randint(1, 100), random.randint(100, 1000))}"
        while frappe.db.exists("Restaurant Object", {"description": name}):
            name = f"{t[:1]}-{random.randint(1, 9999)}"'''
if NEW_TABLE in src:
    print("clean names: add_object already picks a free name")
elif OLD_TABLE in src:
    open(OBJ, "w").write(src.replace(OLD_TABLE, NEW_TABLE, 1))
    print("clean names: add_object picks a free name")
else:
    raise SystemExit("clean names: add_object anchor not found")
