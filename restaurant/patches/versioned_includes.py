# The app's helper scripts (drag.js, frappe-form-class.js, ...) are listed in
# hooks.py app_include_js/app_include_css and emitted as bare /assets URLs, so
# the CDN in front of the site served the pre-deploy copies for up to four
# hours — a "new browser" did not help, the edge is shared. Stamp each include
# with this bake's id: a redeploy renames every URL, and the edge must refetch.
#   python3 versioned_includes.py <stamp>
import re, sys

P = "apps/restaurant_management/restaurant_management/hooks.py"
stamp = sys.argv[1] if len(sys.argv) > 1 else "0"

src = open(P).read()
pattern = re.compile(r"""(["'])(/assets/restaurant_management/[^"'?]+\.(?:js|css))(?:\?v=\d+)?\1""")
new, n = pattern.subn(lambda m: "%s%s?v=%s%s" % (m.group(1), m.group(2), stamp, m.group(1)), src)
if n == 0:
    raise SystemExit("versioned includes: no /assets/restaurant_management includes found in hooks.py")
open(P, "w").write(new)
print("versioned includes: %d include(s) stamped ?v=%s" % (n, stamp))
