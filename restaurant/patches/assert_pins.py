# Fail the bake if an app is not the version we expect. The restaurant app
# tracks master with no tags, so it can move under us at any time; our patches
# anchor on exact source and would either misapply or apply to changed code.
import json
import os

EXPECTED = {}
for line in open("/tmp/PINNED_APPS"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        EXPECTED[k.strip()] = v.strip()

states = json.load(open("sites/apps.json"))
problems = []
for app, want in EXPECTED.items():
    got = states.get(app)
    if not got:
        problems.append("%s: not installed" % app)
        continue
    res = got.get("resolution") or {}
    actual = res.get("commit_hash") or ""
    branch = res.get("branch") or ""
    version = got.get("version") or ""
    if want.startswith("v"):
        # frappe is installed by bench init itself, not through apps.json, so its
        # resolution is empty and only `version` says what actually landed.
        if branch != want and version != want.lstrip("v"):
            problems.append("%s: expected %s, got branch %s / version %s"
                            % (app, want, branch or "?", version or "?"))
    elif actual != want:
        problems.append(
            "%s: expected commit %s, got %s (upstream master moved — review the "
            "diff, re-test, then update restaurant/PINNED_APPS)" % (app, want[:12], (actual or "?")[:12])
        )

if problems:
    raise SystemExit("PINNED APPS MISMATCH\n  " + "\n  ".join(problems))
print("pins ok: " + ", ".join("%s=%s" % (k, v[:12]) for k, v in EXPECTED.items()))
