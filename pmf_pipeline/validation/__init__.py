"""validation/ — one file per check, picked by the user in the GUI.

Each module in this folder is one check: it declares ID, NAME,
DESCRIPTION, SEVERITY ("fail" blocks the export, "warn" doesn't)
and a check(mesh) that returns a result dict. Some checks also
define a repair(mesh) that fixes the problem automatically —
frozen transforms, construction history, origin — and the Repair
button runs those, then re-runs the checks. Checks with no
repair() (manifold, n-gons, zero-area, textures) need a human.
The GUI lists them with checkboxes; Validate and Repair run only
the checked ones. Adding a new check is adding one file here —
nothing else has to change.

The registry below is the only thing that knows the list: it
discovers every public module in this folder (names starting with
"_" are helpers, not checks).
"""
import importlib
import pkgutil


def discover_checks():
    """All check modules in this folder, sorted by ID.

    Returns a list of module objects, each with ID, NAME,
    DESCRIPTION, SEVERITY and check(mesh).
    """
    found = []
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{info.name}")
        found.append(module)
    found.sort(key=lambda m: m.ID)
    return found


def get_check(check_id):
    """One check module by ID, or None."""
    for module in discover_checks():
        if module.ID == check_id:
            return module
    return None


def run_checks(mesh, check_ids=None):
    """Run checks on one mesh transform. check_ids=None runs all.

    Returns a list of result dicts in registry order. A mesh with
    no shape under it fails before any check runs — there is
    nothing to validate.
    """
    from ._common import result, shape_for
    try:
        import maya.cmds as cmds
    except Exception:
        cmds = None
    if cmds is None:
        raise RuntimeError("validation needs Maya (maya.cmds not available)")
    if shape_for(cmds, mesh) is None:
        return [result("mesh-shape", "Mesh shape", "fail", False,
                       f"No mesh shape under {mesh}")]
    modules = discover_checks()
    if check_ids is not None:
        wanted = set(check_ids)
        modules = [m for m in modules if m.ID in wanted]
    return [m.check(mesh) for m in modules]


def run_repairs(mesh, check_ids=None):
    """Run the checks, repair the failing ones that can be repaired,
    then re-run those checks.

    Only some checks define repair(mesh): frozen transforms (freeze),
    construction history (delete history), origin (move the mesh to
    the origin). Manifold / n-gons / zero-area / textures have no
    safe automatic fix — they need a human.

    Returns a list of outcome dicts, one per check, in registry
    order: {"id", "name", "severity", "before", "repair", "after",
    "repaired"}. "before"/"after" are result dicts; "repair" is a
    detail string; "repaired" is whether the check passes after.
    """
    results = run_checks(mesh, check_ids)
    outcomes = []
    for before in results:
        module = get_check(before["id"])
        repair_fn = getattr(module, "repair", None) if module else None
        if before["passed"]:
            outcomes.append({"id": before["id"], "name": before["name"],
                             "severity": before["severity"],
                             "before": before,
                             "repair": "already passing",
                             "after": before, "repaired": True})
            continue
        if repair_fn is None:
            outcomes.append({"id": before["id"], "name": before["name"],
                             "severity": before["severity"],
                             "before": before,
                             "repair": "no automatic fix — fix by hand",
                             "after": before, "repaired": False})
            continue
        try:
            detail = repair_fn(mesh)
        except Exception as e:
            outcomes.append({"id": before["id"], "name": before["name"],
                             "severity": before["severity"],
                             "before": before,
                             "repair": f"repair failed: {e}",
                             "after": before, "repaired": False})
            continue
        after = module.check(mesh)
        outcomes.append({"id": before["id"], "name": before["name"],
                         "severity": before["severity"],
                         "before": before, "repair": detail,
                         "after": after, "repaired": after["passed"]})
    return outcomes


def overall_passed(results):
    """The export gate: every "fail" check passed. Warnings don't block."""
    return all(r["passed"] for r in results if r["severity"] == "fail")
