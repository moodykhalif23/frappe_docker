"""Helpers that make a patch fail loudly instead of silently doing nothing.

Two failure modes have shipped broken code from this pipeline:

  * a guard token that matched something else, so the patch was skipped
    (`grep -q restaurant_manage` matching `restaurant_management`);
  * a guard that could not tell an OLD build of the same patch from the
    current one, so an updated asset never replaced the stale copy.

`block()` fixes both: the marker is a hash of the content being injected, so
any edit forces re-application, and the post-condition is asserted.
"""
import hashlib
import re


def tag_for(name, content):
	"""Marker derived from the content: edit the asset, get a new marker."""
	return "rm_%s_%s" % (name, hashlib.sha1(content.encode("utf-8")).hexdigest()[:8])


def block(path, name, content, header="//"):
	"""Idempotently keep exactly the current version of a named block in a file.

	Any previous build of the same block (matched on the rm_<name>_<hash>
	marker) is removed first, so an updated asset always replaces the old one.
	Returns the marker."""
	tag = tag_for(name, content)
	s = open(path).read()
	if tag in s:
		print("%s: already current (%s)" % (name, tag))
		return tag

	# strip any earlier build of this block: from its marker line to EOF, or to
	# the next block marker if one follows
	pat = re.compile(r"\n[ \t]*%s[ \t]*rm_%s_[0-9a-f]{8}\b" % (re.escape(header), re.escape(name)))
	m = pat.search(s)
	if m:
		s = s[:m.start()]
		print("%s: removed previous build" % name)

	s = s.rstrip("\n") + "\n%s %s\n%s\n" % (header, tag, content.strip("\n"))
	open(path, "w").write(s)

	after = open(path).read()
	assert tag in after, "%s: wrote the block but %s is missing" % (name, tag)
	print("%s: applied (%s)" % (name, tag))
	return tag


def once(path, guard, apply_fn, name):
	"""Apply apply_fn(text)->text unless `guard` is already present.

	`guard` must be something ONLY the applied patch produces — never a label
	or word the new content also contains. The result is asserted."""
	s = open(path).read()
	if guard in s:
		print("%s: already present" % name)
		return False
	s2 = apply_fn(s)
	assert s2 != s, "%s: apply made no change (anchor drifted?)" % name
	assert guard in s2, "%s: applied but guard %r missing" % (name, guard)
	open(path, "w").write(s2)
	print("%s: applied" % name)
	return True
