# The kitchen saw a table and a check number, never who to hand the plate to.
# Two payloads build a ticket — the board's own fetch and the one pushed at
# dispatch — and only the first carried the waiter. The pushed one also left
# room_description out (the board printed "undefined") and passed table_info,
# which upstream returns as a one-item tuple.
OBJ = "apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_object/restaurant_object.py"
ORDER = "apps/restaurant_management/restaurant_management/restaurant_management/doctype/table_order/table_order.py"
JS = "apps/restaurant_management/restaurant_management/public/restaurant/js/process-manage-class.js"

src = open(OBJ).read()
if "waiter=frappe.db.get_value" in src:
    print("ticket waiter: server already sends it")
else:
    OLD = '''            process_status_data=self.process_status_data(entry)
        )'''
    NEW = '''            process_status_data=self.process_status_data(entry),
            waiter=frappe.db.get_value("Table Order", entry.parent, "waiter"),
        )'''
    if OLD not in src:
        raise SystemExit("ticket waiter: get_command_data anchor not found")
    open(OBJ, "w").write(src.replace(OLD, NEW, 1))
    print("ticket waiter: server sends the waiter on every ticket")

# table_info is returned as a tuple upstream, so the pushed ticket rendered the
# table as an array and left the waiter out entirely.
osrc = open(ORDER).read()
TUPLE = """    @property
    def table_info(self):
        return f'{self.room_description} ({self.table_description})',"""
FIXED = """    @property
    def table_info(self):
        return f'{self.room_description} ({self.table_description})'"""
if TUPLE in osrc:
    osrc = osrc.replace(TUPLE, FIXED, 1)
    print("ticket waiter: table_info is a string, not a one-item tuple")

ROW_OLD = '''                row["table_description"] = self.table_info'''
ROW_NEW = '''                row["table_description"] = self.table_info
                # the board prints these; without them the ticket said "undefined"
                row["room_description"] = ""
                row["waiter"] = self.get("waiter")'''
if 'row["waiter"] = self.get("waiter")' in osrc:
    print("ticket waiter: dispatch payload already carries it")
elif ROW_OLD not in osrc:
    raise SystemExit("ticket waiter: dispatch row anchor not found")
else:
    osrc = osrc.replace(ROW_OLD, ROW_NEW, 1)
    print("ticket waiter: the dispatched ticket carries the waiter too")
open(ORDER, "w").write(osrc)

js = open(JS).read()
GOOD_JS = '''  table_info(data) {
    // Whose plate this is: the runner needs it more than the check number.
    const where = data.room_description
      ? `${data.room_description} (${data.table_description})`
      : (data.table_description || "");
    const who = data.waiter
      ? ` <span class="rm-ticket-waiter">${frappe.utils.escape_html(data.waiter)}</span>` : "";
    return `${where}${who}`;
  }'''

if "const where = data.room_description" in js:
    print("ticket waiter: board already shows it")
    raise SystemExit

if "rm-ticket-waiter" in js:
    # an earlier bake printed "undefined" whenever the room was not in the payload
    OLD_JS = '''  table_info(data) {
    // Whose plate this is: the runner needs it more than the check number.
    const who = data.waiter
      ? ` <span class="rm-ticket-waiter">${frappe.utils.escape_html(data.waiter)}</span>` : "";
    return `${data.room_description} (${data.table_description})${who}`;
  }'''
    if OLD_JS not in js:
        raise SystemExit("ticket waiter: cannot upgrade table_info, shape unknown")
    open(JS, "w").write(js.replace(OLD_JS, GOOD_JS, 1))
    print("ticket waiter: board no longer prints undefined for a missing room")
    raise SystemExit

PLAIN_JS = '''  table_info(data) {
    return `${data.room_description} (${data.table_description})`;
  }'''
if PLAIN_JS not in js:
    raise SystemExit("ticket waiter: table_info anchor not found")
open(JS, "w").write(js.replace(PLAIN_JS, GOOD_JS, 1))
print("ticket waiter: board shows it beside the table")
