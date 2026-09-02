# frappe.get_abbr walks word initials, so "Cappuccino (Double)" abbreviated to
# "C(" — a bracket as a product badge. Words that start with a letter only.
P = "apps/restaurant_management/restaurant_management/public/restaurant/js/product-item-class.js"

src = open(P).read()
if "RM_item_abbr" in src:
    # an earlier bake abbreviated "1/4 Chicken Wings" to digits
    OLD_FN = 'const words = String(title || "").split(/[^A-Za-z0-9]+/).filter(Boolean);'
    NEW_FN = ('const all = String(title || "").split(/[^A-Za-z0-9]+/).filter(Boolean);\n'
              '  const words = all.filter(w => /[A-Za-z]/.test(w)).length '
              '? all.filter(w => /[A-Za-z]/.test(w)) : all;')
    if OLD_FN in src:
        open(P, "w").write(src.replace(OLD_FN, NEW_FN, 1))
        print("card initials: abbr now prefers letters")
    else:
        print("card initials: already applied")
    raise SystemExit

OLD = '''frappe.get_abbr(item_title)}</span>`}'''
NEW = '''window.RM_item_abbr(item_title)}</span>`}'''
if OLD not in src:
    raise SystemExit("card initials: abbr anchor not found")

HELPER = '''
// RM_item_abbr: initials a waiter can read — letters only, never a bracket.
window.RM_item_abbr = function (title) {
  const all = String(title || "").split(/[^A-Za-z0-9]+/).filter(Boolean);
  // "1/4 Chicken Wings" reads as CW, not 14: letters identify a dish, digits do not
  const words = all.filter(w => /[A-Za-z]/.test(w)).length ? all.filter(w => /[A-Za-z]/.test(w)) : all;
  if (!words.length) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
};
'''
open(P, "w").write(src.replace(OLD, NEW, 1) + HELPER)
print("card initials: letters only")
