"""A sale is voided by cancelling, never deleted: the guards refuse the delete,
the series never hands a number back, Release keeps the check, and the drawer is
counted. Test sites only — it seats a check and releases a table."""
import json
import frappe
from restaurant_management import house

PASSED = []


def ok(name, cond, detail=""):
	PASSED.append(bool(cond))
	print("%s  %s%s" % ("PASS" if cond else "FAIL", name, ("   [%s]" % detail) if detail else ""))


def refused(fn):
	"""The message the guard threw, or "" if the delete went through."""
	try:
		fn()
		return ""
	except Exception as e:
		return str(e) or e.__class__.__name__
	finally:
		frappe.db.rollback()


def _series_after_revert(key):
	# tabSeries has no creation column, so frappe's own code reads it in raw SQL
	from frappe.model.naming import make_autoname, revert_series_if_last
	prefix = key.split(".")[0]
	drop = lambda: frappe.db.sql("delete from tabSeries where name=%s", prefix)
	current = lambda: frappe.utils.cint((frappe.db.sql(
		"select `current` from tabSeries where name=%s", prefix) or [[0]])[0][0])
	drop()
	name = make_autoname(key)
	before = current()
	revert_series_if_last(key, name)
	after = current()
	drop()
	return before, after


def run():
	frappe.set_user("Administrator")

	events = frappe.get_hooks("doc_events") or {}
	wired = [dt for dt in ("POS Invoice", "Sales Invoice", "POS Closing Entry", "Table Order")
			 if "refuse_delete" in str((events.get(dt) or {}).get("on_trash") or "")]
	ok("the guard is wired on every money document and on checks", len(wired) == 4, json.dumps(wired))

	for dt in ("POS Invoice", "Sales Invoice", "POS Closing Entry"):
		found = frappe.get_all(dt, limit=1, pluck="name")
		if not found:
			continue
		# a submitted document is refused by frappe's core before on_trash ever fires;
		msg = refused(lambda: frappe.delete_doc(dt, found[0], force=1, ignore_permissions=True))
		ok("%s %s cannot be deleted" % (dt, found[0]), bool(msg), msg[:110] or "it was deleted")
		guard = refused(lambda: house.refuse_delete(frappe.get_doc(dt, found[0])))
		ok("and our guard refuses it whatever its docstatus", "cancel it instead" in guard, guard[:120])

	before, after = _series_after_revert("ZZTESTSER-.#####")
	ok("an ordinary series still rewinds — upstream behaviour is untouched", after == before - 1,
	   "was %s, now %s" % (before, after))
	before, after = _series_after_revert("ACC-PSINV-9999-.#####")
	ok("a deleted invoice number is never handed back", after == before, "was %s, now %s" % (before, after))
	before, after = _series_after_revert("OR-9999-.#####")
	ok("nor a deleted check number", after == before, "was %s, now %s" % (before, after))
	frappe.db.commit()

	# the same lookup day_float uses: house_shift() also accepts a draft entry
	if not house._open_shift_doc(None):
		house.open_day(balances=json.dumps({"Cash": 5000}))
		frappe.db.commit()

	shift = house._open_shift_doc(None)
	floats = house.day_float()
	ok("the close dialog is told what the till should hold",
	   bool(floats) and all("expected" in r and "mode_of_payment" in r for r in floats),
	   json.dumps(floats)[:150])
	ok("expected is the float counted in plus what was rung on that mode",
	   all(abs(r["expected"] - (r["opening"] + r["sales"])) < 0.01 for r in floats),
	   json.dumps(floats)[:150])
	ok("every mode the float went into is asked about, sales or no sales",
	   set(house._shift_floats(shift)) <= {r["mode_of_payment"] for r in floats},
	   json.dumps(house._shift_floats(shift)))

	from erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry import make_closing_entry_from_opening
	draft = make_closing_entry_from_opening(shift)
	want = floats[0]
	mode = want["mode_of_payment"]
	house._record_counted_drawer(draft, json.dumps({mode: want["expected"] + 250}))
	row = [r for r in draft.payment_reconciliation if r.mode_of_payment == mode][0]
	ok("a drawer counted 250 over reads as 250 over, not as a nil difference",
	   abs(row.difference - 250) < 0.01 and abs(row.closing_amount - (want["expected"] + 250)) < 0.01,
	   "closing=%s expected=%s difference=%s" % (row.closing_amount, row.expected_amount, row.difference))
	ok("and the closing entry records the float instead of leaving it at zero",
	   abs(frappe.utils.flt(row.opening_amount) - want["opening"]) < 0.01
	   and abs(frappe.utils.flt(row.expected_amount) - want["expected"]) < 0.01,
	   "opening=%s expected=%s (float %s + sales %s)" % (row.opening_amount, row.expected_amount,
														 want["opening"], want["sales"]))
	import inspect
	ok("close_day takes the counted drawer", "counted" in inspect.signature(house.close_day).parameters)

	table = [t["name"] for t in house.free_tables()
			 if not str(t.get("description", "")).startswith("Delivery")][0]
	seat = house.seat_walkin("ZZ Test Void", 2, table, waiter="Amina Test", pin="1111")
	order = seat["order"]
	doc = frappe.get_doc("Table Order", order)
	menu = frappe.db.get_value("POS Profile", {"disabled": 0}, "restaurant_menu")
	item = frappe.get_all("Restaurant Menu Item", filters={"parent": menu, "status": 1},
						  fields=["item"], limit=1)[0].item
	rate = float(frappe.db.get_value("Item Price", {"item_code": item, "selling": 1}, "price_list_rate") or 100)
	doc.push_item(dict(name=None, entry_name=None, identifier=frappe.generate_hash(length=10), item_code=item,
					   item_name=frappe.db.get_value("Item", item, "item_name"), qty=1, rate=rate,
					   price_list_rate=rate, discount_percentage=0, discount_amount=0,
					   stock_uom=frappe.db.get_value("Item", item, "stock_uom"), item_invoice=None,
					   item_invoice_name=None, ordered_time=None, has_serial_no=0, serial_no=None,
					   has_batch_no=0, batch_no=None, status="Attending", notes=""))
	frappe.db.commit()
	try:
		house.dispatch(order, "Amina Test", pin="1111")
	except Exception as e:
		# no production centre wired on this site: the guard reads the line's status
		for line in frappe.get_all("Order Entry Item", filters={"parent": order}, pluck="name"):
			frappe.db.set_value("Order Entry Item", line, "status", "Sent", update_modified=False)
		print("      (dispatch unavailable, status set directly: %s)" % str(e)[:80])
	frappe.db.commit()
	fired = frappe.db.count("Order Entry Item",
							{"parent": order, "status": ["not in", ["Pending", "Attending"]]})
	ok("the check carries a line the kitchen has seen", fired >= 1, "fired=%s" % fired)

	msg = refused(lambda: frappe.delete_doc("Table Order", order, force=1, ignore_permissions=True))
	ok("a check with food on it cannot be deleted", "already sent to the kitchen" in msg,
	   msg[:130] or "it was deleted")

	house.release_table(table)
	frappe.db.commit()
	state = frappe.db.get_value("Table Order", order, ["status", "show_in_pos"], as_dict=True)
	ok("Release keeps the record instead of erasing it", bool(state), "" if state else "the check is gone")
	ok("Release marks it Cancelled and takes it off the floor",
	   bool(state) and state.status == "Cancelled" and not state.show_in_pos, json.dumps(state or {}))
	ok("the food that was ordered is still on the record",
	   frappe.db.count("Order Entry Item", {"parent": order, "qty": [">", 0]}) >= 1)
	ok("and the table is free for the next party",
	   table in [t["name"] for t in house.free_tables()])

	print("%d/%d passed" % (sum(PASSED), len(PASSED)))
	if not all(PASSED):
		raise AssertionError("void not delete suite failed")
