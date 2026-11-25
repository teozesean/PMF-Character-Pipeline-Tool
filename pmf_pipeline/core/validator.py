"""validator.py — thin layer over pmf_pipeline.validation.

Each check lives in its own file under validation/ (manifold.py,
ngon.py, ...) so the GUI can list them with checkboxes. This module
keeps the old API — check_mesh / validate_selection / format_report
— so existing callers don't change.

Result: {"passed": bool, "checks": [{"id", "name", "severity",
"passed", "detail", "nodes": [...]}]}. "passed" is the export
gate: every "fail" check passed; warnings don't block.
"""
try:
    import maya.cmds as cmds
except Exception:  # outside Maya — functions raise a clear error
    cmds = None

from ..validation import overall_passed, run_checks, run_repairs


def _require_maya():
    if cmds is None:
        raise RuntimeError("validator needs Maya (maya.cmds not available)")


def check_mesh(mesh_transform, check_ids=None):
    """Validate one mesh transform. check_ids=None runs every check."""
    _require_maya()
    results = run_checks(mesh_transform, check_ids)
    return {"passed": overall_passed(results), "checks": results}


def format_report(result):
    lines = []
    for c in result["checks"]:
        if c["passed"]:
            mark = "PASS"
        elif c["severity"] == "warn":
            mark = "WARN"
        else:
            mark = "FAIL"
        lines.append(f"[{mark}] {c['name']}: {c['detail']}")
    lines.append("OVERALL: PASS — safe to export" if result["passed"]
                 else "OVERALL: FAIL — fix the FAIL items before Unity export")
    return "\n".join(lines)


def format_repair_report(outcomes):
    """One line per check after a Repair run, plus the export gate.

    outcomes are the dicts run_repairs returns. Checks that passed
    already say so; repaired ones say what was done; checks with
    no automatic fix say they need a human.
    """
    lines = []
    for o in outcomes:
        if o["before"]["passed"]:
            lines.append(f"[OK] {o['name']}: already passing")
        elif o["repaired"]:
            lines.append(f"[REPAIRED] {o['name']}: {o['repair']} — now passes")
        elif o["repair"].startswith("no automatic fix"):
            lines.append(f"[MANUAL] {o['name']}: {o['repair']} "
                         f"(still failing: {o['after']['detail']})")
        else:
            lines.append(f"[FAILED] {o['name']}: {o['repair']} "
                         f"(still failing: {o['after']['detail']})")
    after = [o["after"] for o in outcomes]
    lines.append("OVERALL: PASS — safe to export" if overall_passed(after)
                 else "OVERALL: FAIL — fix the remaining items before Unity export")
    return "\n".join(lines)


def repair_selection(check_ids=None):
    """Repair the failing CHECKED checks on every selected mesh.

    Returns {mesh: outcomes}, where outcomes are the dicts
    run_repairs returns. Only checks with a repair() are fixed;
    the rest are reported as needing a human.
    """
    _require_maya()
    sel = cmds.ls(selection=True, type="transform") or []
    meshes = [s for s in sel
              if cmds.listRelatives(s, shapes=True, type="mesh")]
    if not meshes:
        meshes = cmds.ls(type="mesh")
        meshes = [cmds.listRelatives(m, parent=True)[0] for m in meshes]
    return {m: run_repairs(m, check_ids) for m in meshes}


def validate_selection(check_ids=None):
    """Validate every selected mesh transform. Returns {mesh: result}."""
    _require_maya()
    sel = cmds.ls(selection=True, type="transform") or []
    meshes = [s for s in sel
              if cmds.listRelatives(s, shapes=True, type="mesh")]
    if not meshes:
        meshes = cmds.ls(type="mesh")
        meshes = [cmds.listRelatives(m, parent=True)[0] for m in meshes]
    return {m: check_mesh(m, check_ids) for m in meshes}
