# frappe's FieldGroup.make() applies each field's default AFTER the record has
# loaded — and get_field_default_value returns an empty default for NUMERIC
# fields (it ignores it for text). So "Update Table" opened with the seat count
# blank while the description showed, and saving posted null: seats wiped to 0.
# Put the record's values back over the defaults once the form is made.
P = "apps/restaurant_management/restaurant_management/public/helper/js/frappe-form-class.js"

src = open(P).read()
if "rm_record_values" in src:
    print("form keeps record values: already applied")
    raise SystemExit

OLD_INIT = "\t\tthis.doc = JSON.parse(JSON.stringify(this.doc || {}));\n"
NEW_INIT = ("\t\tthis.doc = JSON.parse(JSON.stringify(this.doc || {}));\n"
            "\t\tthis._rm_record = JSON.parse(JSON.stringify(this.doc));   // rm_record_values\n")
if src.count(OLD_INIT) != 1:
    raise SystemExit("form keeps record values: initialize anchor found %d times" % src.count(OLD_INIT))
src = src.replace(OLD_INIT, NEW_INIT, 1)

OLD_MAKE = "\t\t\tsuper.make();\n"
NEW_MAKE = """\t\t\tsuper.make();

\t\t\t// rm_record_values: the defaults frappe applies here blank every numeric
\t\t\t// field whose default is empty; the record's own values win.
\t\t\tif (this.doc_name && this._rm_record) {
\t\t\t\tsetTimeout(() => {
\t\t\t\t\tconst vals = {};
\t\t\t\t\t(this.desk_form.desk_form_fields || []).forEach(df => {
\t\t\t\t\t\tconst v = df.fieldname && this._rm_record[df.fieldname];
\t\t\t\t\t\tif (df.fieldname && this.fields_dict[df.fieldname] && v !== undefined && v !== null) vals[df.fieldname] = v;
\t\t\t\t\t});
\t\t\t\t\tthis.set_values(vals);
\t\t\t\t}, 0);
\t\t\t}
"""
if src.count(OLD_MAKE) != 1:
    raise SystemExit("form keeps record values: super.make anchor found %d times" % src.count(OLD_MAKE))
open(P, "w").write(src.replace(OLD_MAKE, NEW_MAKE, 1))
print("form keeps record values: a dialog shows and keeps the record's numbers")
