# desk_form.accept writes every field of the form onto the document, taking a
# missing key as None. Save the Update Table dialog before its values have
# loaded (a slow link, an eager tap) and the seat count is wiped to 0. When
# updating an existing record, a field the client did not send stays as it is.
P = "apps/restaurant_management/restaurant_management/restaurant_management/doctype/desk_form/desk_form.py"

src = open(P).read()
if "rm_partial_save" in src:
    print("desk form partial save: already applied")
    raise SystemExit

OLD = """		df = meta.get_field(fieldname)
		value = data.get(fieldname, None)
"""
NEW = """		df = meta.get_field(fieldname)
		# rm_partial_save: an existing record keeps what the form did not send
		if doc_name and fieldname not in data:
			continue
		value = data.get(fieldname, None)
"""
if src.count(OLD) != 1:
    raise SystemExit("desk form partial save: field loop anchor not found (%d)" % src.count(OLD))
open(P, "w").write(src.replace(OLD, NEW, 1))
print("desk form partial save: unsent fields are left alone on update")
