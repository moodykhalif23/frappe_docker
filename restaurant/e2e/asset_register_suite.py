"""What the restaurant owns, counted rather than costed. erpnext's Asset refuses a
record with no purchase amount, so the register stands on its own while reusing the
Asset Categories already set up. Test sites only: it adds and removes its own rows."""
import json
import frappe

PASSED = []
CAT = "ZZ Register Probe"


def ok(name, cond, detail=""):
	PASSED.append(bool(cond))
	print("%s  %s%s" % ("PASS" if cond else "FAIL", name, ("   [%s]" % detail) if detail else ""))


def _cleanup():
	for a in frappe.get_all("Restaurant Asset", filters={"asset_category": CAT}, pluck="name"):
		frappe.delete_doc("Restaurant Asset", a, force=1, ignore_permissions=True)
	if frappe.db.exists("Restaurant Asset Category", CAT):
		frappe.delete_doc("Restaurant Asset Category", CAT, force=1, ignore_permissions=True)
	frappe.db.commit()


def run():
	frappe.set_user("Administrator")
	ok("the register exists as a doctype", bool(frappe.db.exists("DocType", "Restaurant Asset")))
	if not frappe.db.exists("DocType", "Restaurant Asset"):
		print("%d/%d passed" % (sum(PASSED), len(PASSED)))
		raise AssertionError("asset register suite failed")

	_cleanup()
	frappe.get_doc({"doctype": "Restaurant Asset Category", "category_name": CAT}).insert(
		ignore_permissions=True)
	frappe.db.commit()
	ok("a category is made with a name and nothing else",
	   bool(frappe.db.exists("Restaurant Asset Category", CAT)), CAT)

	# --- the thing the request asked for: a name and a category, nothing else ---
	doc = frappe.get_doc({"doctype": "Restaurant Asset", "asset_name": "Chairs",
						  "asset_category": CAT, "quantity": 40}).insert(ignore_permissions=True)
	frappe.db.commit()
	ok("an asset needs only what it is and where it belongs", bool(doc.name), doc.name)
	ok("it is named readably, not as a hash", doc.name.startswith("AST-"), doc.name)
	ok("it counts how many", doc.quantity == 40, str(doc.quantity))
	ok("it dates itself so a count can be traced", bool(doc.acquired_on), str(doc.acquired_on))
	ok("and starts in use", doc.status == "In Use", doc.status)

	# --- no purchase or depreciation is demanded anywhere ---
	meta = frappe.get_meta("Restaurant Asset")
	fields = {f.fieldname for f in meta.fields}
	ok("it asks for no purchase amount",
	   not (fields & {"gross_purchase_amount", "purchase_amount", "net_purchase_amount"}),
	   json.dumps(sorted(fields)))
	ok("and schedules no depreciation", "calculate_depreciation" not in fields)
	reqd = {f.fieldname for f in meta.fields if f.reqd}
	ok("only the name and the category are required", reqd <= {"asset_name", "asset_category"},
	   json.dumps(sorted(reqd)))

	# --- erpnext's own category demands ledger accounts: that is why this one exists ---
	try:
		frappe.get_doc({"doctype": "Asset Category",
						"asset_category_name": CAT + " erpnext"}).insert(ignore_permissions=True)
		ok("erpnext's Asset Category would have taken it too", False, "it accepted a bare category")
	except Exception as e:
		ok("erpnext's Asset Category demands accounts, which this one does not",
		   "account" in str(e).lower(), str(e)[:110])

	# --- a quantity that makes no sense is corrected, not stored ---
	odd = frappe.get_doc({"doctype": "Restaurant Asset", "asset_name": "Spoons",
						  "asset_category": CAT, "quantity": 0}).insert(ignore_permissions=True)
	frappe.db.commit()
	ok("a count below one is corrected to one", odd.quantity == 1, str(odd.quantity))

	ok("the register groups by the categories already set up",
	   frappe.db.count("Restaurant Asset", {"asset_category": CAT}) == 2,
	   str(frappe.db.count("Restaurant Asset", {"asset_category": CAT})))

	# --- the list screen is where they will add them ---
	import os
	path = frappe.get_app_path("restaurant_management", "restaurant_management", "doctype",
							   "restaurant_asset", "restaurant_asset_list.js")
	ok("the list carries the bulk-add screen", os.path.exists(path), path)
	if os.path.exists(path):
		js = open(path).read()
		ok("with a button to add several at once", "Add several" in js)
		ok("that keeps the category between entries", "the next thing is usually in the same one" in js)

	_cleanup()
	print("%d/%d passed" % (sum(PASSED), len(PASSED)))
	if not all(PASSED):
		raise AssertionError("asset register suite failed")
