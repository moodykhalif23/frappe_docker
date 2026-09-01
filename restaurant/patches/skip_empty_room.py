# The floor remembers the last room opened. If that room has no tables it looks
# broken — the same panic an empty R 4 caused on the live floor.
P = "apps/restaurant_management/restaurant_management/restaurant_management/page/restaurant_manage/restaurant_manage.js"

src = open(P).read()
if "rm_skip_empty_room" in src:
    print("empty room: already applied")
    raise SystemExit

ANCHOR = "  make_rooms() {"
BLOCK = '''  // rm_skip_empty_room: never open on a room with nothing in it.
  first_room_with_tables() {
    let best = null;
    this.in_rooms((room) => {
      const count = room.child_count || 0;
      if (!best && count > 0) best = room;
    });
    return best;
  }

  make_rooms() {'''

if ANCHOR not in src:
    raise SystemExit("empty room: make_rooms anchor not found")
src = src.replace(ANCHOR, BLOCK, 1)

OLD_SEL = "            }, 100);"
NEW_SEL = '''            }, 100);
            setTimeout(() => {
              const current = this.current_room;
              if (current && (current.child_count || 0) > 0) return;
              const room = this.first_room_with_tables();
              if (room && room.select) room.select();
            }, 2500);'''
if src.count(OLD_SEL) < 1:
    raise SystemExit("empty room: permissions timeout anchor not found")
open(P, "w").write(src.replace(OLD_SEL, NEW_SEL, 1))
print("empty room: the floor opens where the tables are")
