# After seating a guest the page navigates to that party's room. If the room is
# not among this user's objects the unguarded select() threw, and the floor then
# never repainted — a waiter tablet stuck showing the old tiles.
P = ("apps/restaurant_management/restaurant_management/restaurant_management/"
     "page/restaurant_manage/restaurant_manage.js")

src = open(P).read()
OLD = """    RM.objects[navigate].select();"""
NEW = """    RM.objects[navigate] && RM.objects[navigate].select();"""

if NEW in src:
    print("navigate guard: already applied")
elif OLD not in src:
    raise SystemExit("navigate guard: navigate_room anchor not found")
else:
    open(P, "w").write(src.replace(OLD, NEW, 1))
    print("navigate guard: an unknown room no longer breaks the floor")
