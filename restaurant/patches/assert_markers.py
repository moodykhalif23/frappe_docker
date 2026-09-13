"""Fail the bake if any patch silently did nothing.

Every patch here guards itself with a string match. A guard that matches the
wrong thing, or that cannot tell its own older output from the current build,
skips without complaint — the build goes green and ships stale code. That has
happened twice. This is the end-state check: it runs LAST, and asserts the
image actually contains what every patch was supposed to produce.
"""
import sys

problems = []
checked = 0

MANIFEST = sys.argv[1] if len(sys.argv) > 1 else "/tmp/PATCH_MANIFEST"

for raw in open(MANIFEST):
	line = raw.strip()
	if not line or line.startswith("#"):
		continue
	if "::" not in line:
		problems.append("manifest line is not <path> :: <marker>: %s" % line)
		continue
	path, marker = line.split("::", 1)
	path, marker = path.strip(), marker.strip()
	checked += 1
	try:
		body = open(path, encoding="utf-8", errors="replace").read()
	except OSError as e:
		problems.append("%s: cannot read (%s)" % (path, e.__class__.__name__))
		continue
	if marker not in body:
		problems.append("%s: MISSING %r" % (path, marker))

if problems:
	print("\n*** patch verification FAILED — the bake produced an image that is "
		  "missing %d of %d expected markers ***\n" % (len(problems), checked))
	for p in problems:
		print("  - %s" % p)
	print("\nA patch guard probably matched the wrong thing and skipped, or an "
		  "anchor drifted after an upstream change. Fix the patch — do not "
		  "delete the manifest line.\n")
	sys.exit(1)

print("patch verification OK: %d markers present" % checked)
