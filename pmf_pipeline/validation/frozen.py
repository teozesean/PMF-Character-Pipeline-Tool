"""frozen.py — transforms frozen on the mesh.

A mesh whose translate/rotate aren't zeroed and scale isn't 1
carries a hidden offset into Unity: the character spawns rotated
or scaled, and the rig's bind pose won't match. Warning only —
it doesn't block the export, but freeze it before you ship.
"""
try:
    import maya.cmds as cmds
except Exception:  # outside Maya — check() raises a clear error
    cmds = None

from ._common import result, shape_for

ID = "frozen"
NAME = "Frozen transforms"
DESCRIPTION = ("Translate/rotate zeroed, scale at 1. An unfrozen "
               "mesh carries a hidden offset into Unity.")
SEVERITY = "warn"


def _require_maya():
    if cmds is None:
        raise RuntimeError("frozen check needs Maya (maya.cmds not available)")


def check(mesh):
    """Validate one mesh transform. Returns a result dict."""
    _require_maya()
    if shape_for(cmds, mesh) is None:
        return result(ID, NAME, SEVERITY, False,
                      f"No mesh shape under {mesh}")

    t = cmds.xform(mesh, q=True, translation=True)
    r = cmds.xform(mesh, q=True, rotation=True)
    s = cmds.xform(mesh, q=True, scale=True)
    frozen = (t == [0, 0, 0] and r == [0, 0, 0] and s == [1, 1, 1])
    return result(ID, NAME, SEVERITY, frozen,
                  "frozen" if frozen else f"not frozen: t={t} r={r} s={s}")


def repair(mesh):
    """Freeze the mesh's transforms (zero t/r, scale 1).

    Returns a detail string for the repair log. The caller re-runs
    check() afterwards to confirm it actually passes now.
    """
    _require_maya()
    cmds.makeIdentity(mesh, apply=True, translate=True,
                      rotate=True, scale=True)
    return "froze transforms (translate/rotate zeroed, scale 1)"
