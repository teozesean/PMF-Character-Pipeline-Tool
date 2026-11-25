"""origin.py — the mesh stands on the world origin.

A game character should be centred on the origin (X/Z) with its
feet on the ground (Y=0), so Unity spawns it in the right place.
This reads the mesh's bounding box: centre X/Z near 0, min Y near
0. Tolerance is 1 cm (Maya works in cm). Warning only — a mesh
can be re-centred in Unity, but it shouldn't have to be.
"""
try:
    import maya.cmds as cmds
except Exception:  # outside Maya — check() raises a clear error
    cmds = None

from ._common import result, shape_for

ID = "origin"
NAME = "Mesh at origin"
DESCRIPTION = ("Bounding box centred on the origin (X/Z) with feet "
               "on Y=0, so Unity spawns the character in the right "
               "place. Tolerance 1 cm.")
SEVERITY = "warn"

TOLERANCE = 0.01


def _require_maya():
    if cmds is None:
        raise RuntimeError("origin check needs Maya (maya.cmds not available)")


def check(mesh):
    """Validate one mesh transform. Returns a result dict."""
    _require_maya()
    if shape_for(cmds, mesh) is None:
        return result(ID, NAME, SEVERITY, False,
                      f"No mesh shape under {mesh}")

    xmin, ymin, zmin, xmax, ymax, zmax = cmds.xform(
        mesh, q=True, boundingBox=True)
    cx = (xmin + xmax) / 2
    cz = (zmin + zmax) / 2
    issues = []
    if abs(cx) > TOLERANCE or abs(cz) > TOLERANCE:
        issues.append(f"off-centre by ({cx:.2f}, {cz:.2f})")
    if abs(ymin) > TOLERANCE:
        issues.append(f"feet at Y={ymin:.2f}, not on the ground")
    passed = not issues
    return result(ID, NAME, SEVERITY, passed,
                  "centred at origin" if passed else "; ".join(issues))


def repair(mesh):
    """Move the mesh so its bounding box is centred on the origin
    (X/Z) with its feet on Y=0.

    Returns a detail string for the repair log. The caller re-runs
    check() afterwards to confirm it actually passes now. Note
    this moves the mesh transform itself — do it before skinning,
    not on a bound character mesh.
    """
    _require_maya()
    xmin, ymin, zmin, xmax, ymax, zmax = cmds.xform(
        mesh, q=True, boundingBox=True)
    cx = (xmin + xmax) / 2
    cz = (zmin + zmax) / 2
    cmds.xform(mesh, translation=[-cx, -ymin, -cz], relative=True)
    return (f"moved to origin (was off-centre by ({cx:.2f}, {cz:.2f}), "
            f"feet at Y={ymin:.2f})")
