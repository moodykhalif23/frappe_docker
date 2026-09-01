# The kitchen saw a table and a check number, never who to hand the plate to.
OBJ = "apps/restaurant_management/restaurant_management/restaurant_management/doctype/restaurant_object/restaurant_object.py"
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

js = open(JS).read()
if "rm-ticket-waiter" in js:
    print("ticket waiter: board already shows it")
    raise SystemExit

OLD_JS = '''  table_info(data) {
    return `${data.room_description} (${data.table_description})`;
  }'''
NEW_JS = '''  table_info(data) {
    // Whose plate this is: the runner needs it more than the check number.
    const who = data.waiter
      ? ` <span class="rm-ticket-waiter">${frappe.utils.escape_html(data.waiter)}</span>` : "";
    return `${data.room_description} (${data.table_description})${who}`;
  }'''
if OLD_JS not in js:
    raise SystemExit("ticket waiter: table_info anchor not found")
open(JS, "w").write(js.replace(OLD_JS, NEW_JS, 1))
print("ticket waiter: board shows it beside the table")
