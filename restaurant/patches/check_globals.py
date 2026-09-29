# check_globals.py — fail the build when a patched Python module calls a global
# name it never defines.
#
# Why: bakes build FROM their own output, and the dockerfile cuts table_order.py
# back to its appended waiter block before re-appending it. A helper a patch had
# appended after that block vanished on the next bake while the patch's guard
# (a marker still present elsewhere in the file) skipped re-adding it — so send()
# would have called a function that no longer existed, and every Order press
# would have thrown NameError. ast.parse and the marker manifest both pass that.
#
# Static on purpose: compiles the source, walks every code object for
# LOAD_GLOBAL, and checks each name against what the module binds at top level
# plus builtins. No import, so it needs neither frappe nor a site.
#
#   python3 check_globals.py path/to/module.py [more.py ...]
import ast, builtins, dis, sys


def bound_names(tree):
    names = set()

    def targets(node):
        for n in ast.walk(node):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                names.add(n.id)

    def visit(stmts):
        for st in stmts:
            if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(st.name)
            elif isinstance(st, (ast.Import, ast.ImportFrom)):
                for a in st.names:
                    if a.name == "*":
                        names.add("*")
                    else:
                        names.add(a.asname or a.name.split(".")[0])
            elif isinstance(st, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                for t in (st.targets if isinstance(st, ast.Assign) else [st.target]):
                    targets(t)
            elif isinstance(st, (ast.For, ast.AsyncFor)):
                targets(st.target); visit(st.body); visit(st.orelse)
            elif isinstance(st, (ast.With, ast.AsyncWith)):
                for it in st.items:
                    if it.optional_vars is not None:
                        targets(it.optional_vars)
                visit(st.body)
            elif isinstance(st, ast.If):
                visit(st.body); visit(st.orelse)
            elif isinstance(st, ast.Try):
                visit(st.body); visit(st.orelse); visit(st.finalbody)
                for h in st.handlers:
                    if h.name:
                        names.add(h.name)
                    visit(h.body)
            elif isinstance(st, ast.Global):
                names.update(st.names)
    visit(tree.body)
    # a `global x` inside a function that assigns x also binds it at module level
    for n in ast.walk(tree):
        if isinstance(n, ast.Global):
            names.update(n.names)
    return names


def global_loads(code, out):
    for ins in dis.get_instructions(code):
        if ins.opname == "LOAD_GLOBAL":
            out.add((ins.argval, code.co_name))
    for c in code.co_consts:
        if hasattr(c, "co_code"):
            global_loads(c, out)


bad = 0
for path in sys.argv[1:]:
    src = open(path).read()
    tree = ast.parse(src, path)
    have = bound_names(tree) | set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__spec__", "__builtins__"}
    if "*" in have:
        print("check_globals: %s has a star import, skipped" % path)
        continue
    loads = set()
    global_loads(compile(src, path, "exec"), loads)
    missing = sorted({(n, f) for n, f in loads if n not in have})
    for n, f in missing:
        print("check_globals: %s: %s() uses undefined global %r" % (path, f, n))
    bad += len(missing)
    if not missing:
        print("check_globals: %s ok (%d global references)" % (path, len(loads)))
sys.exit(1 if bad else 0)
