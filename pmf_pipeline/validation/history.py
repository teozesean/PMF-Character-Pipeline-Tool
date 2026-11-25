"""history.py — construction history still present.

A mesh with live construction history (polyCube, extrude, smooth
nodes still in the chain) exports fine, but the history can change
the mesh later and bloats the file. Warning only — delete history
before you ship.
"""
try:
    import maya.cmds as cmds
except Exception:  # outside Maya — check() raises a clear error
    cmds = None

from ._common import result, shape_for

ID = "history"
NAME = "No construction history"
DESCRIPTION = ("Live construction history (extrude/smooth nodes) "
               "still in the chain. Delete history before shipping.")
SEVERITY = "warn"


def _require_maya():
    if cmds is None:
        raise RuntimeError("history check needs Maya (maya.cmds not available)")


def check(mesh):
    """Validate one mesh transform. Returns a result dict."""
    _require_maya()
    shape = shape_for(cmds, mesh)
    if shape is None:
        return result(ID, NAME, SEVERITY, False,
                      f"No mesh shape under {mesh}")

    history = [h for h in (cmds.listHistory(mesh) or [])
               if h not in (mesh, shape)]
    passed = not history
    return result(ID, NAME, SEVERITY, passed,
                  "no history" if passed
                  else f"history present: {', '.join(history[:5])}",
                  history)


def repair(mesh):
    """Delete the mesh's construction history.

    Returns a detail string for the repair log. The caller re-runs
    check() afterwards to confirm it actually passes now.
    """
    _require_maya()
    cmds.delete(mesh, constructionHistory=True)
    return "deleted construction history"
