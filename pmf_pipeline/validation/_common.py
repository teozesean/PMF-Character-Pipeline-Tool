"""_common.py — shared helpers for the validation checks.

Not a check itself (the underscore keeps it out of discovery).
Every check module imports from here so they all report the same
result shape and resolve the mesh shape the same way.
"""


def shape_for(cmds, mesh_transform):
    """The mesh shape node under a transform, or None.

    A transform with no mesh shape under it fails the gate outright
    — there is nothing to validate — so the registry reports it
    before running any check.
    """
    shapes = cmds.listRelatives(mesh_transform, shapes=True, type="mesh") or []
    return shapes[0] if shapes else None


def result(check_id, name, severity, passed, detail="", nodes=None):
    """One check's result. Severity is "fail" (blocks the export)
    or "warn" (reported, doesn't block)."""
    return {
        "id": check_id,
        "name": name,
        "severity": severity,
        "passed": bool(passed),
        "detail": detail,
        "nodes": list(nodes or []),
    }
