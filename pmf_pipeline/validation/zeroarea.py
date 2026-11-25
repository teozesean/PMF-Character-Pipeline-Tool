"""zeroarea.py — faces with no area (collapsed faces).

A face whose vertices repeat, or that has fewer than 3 distinct
vertices, has no area: it breaks normals and skinning. This check
reads the vertex list per face from polyInfo -faceToVertex and
flags the degenerate ones.

Limitation, stated honestly: this catches collapsed faces, not a
face that is merely tiny. True per-face area needs an MFnMesh pass
(MFnMesh.getPolygonArea) — that is a follow-up, not this file.
"""
import re

try:
    import maya.cmds as cmds
except Exception:  # outside Maya — check() raises a clear error
    cmds = None

from ._common import result, shape_for

ID = "zeroarea"
NAME = "No zero-area faces"
DESCRIPTION = ("Faces with no area (collapsed or duplicate vertices). "
               "Catches degenerate faces; true per-face area needs "
               "an MFnMesh pass (follow-up).")
SEVERITY = "fail"

_FACE_RE = re.compile(r"FACE\s+(\d+)\s*:\s*(.*)")


def _require_maya():
    if cmds is None:
        raise RuntimeError("zeroarea check needs Maya (maya.cmds not available)")


def check(mesh):
    """Validate one mesh transform. Returns a result dict."""
    _require_maya()
    shape = shape_for(cmds, mesh)
    if shape is None:
        return result(ID, NAME, SEVERITY, False,
                      f"No mesh shape under {mesh}")

    bad = []
    for row in cmds.polyInfo(shape, faceToVertex=True) or []:
        m = _FACE_RE.match(str(row))
        if not m:
            continue
        verts = m.group(2).split()
        if len(set(verts)) < 3:
            bad.append(f"face {m.group(1)}")
    passed = not bad
    return result(ID, NAME, SEVERITY, passed,
                  "no degenerate faces" if passed
                  else f"{len(bad)} degenerate face(s): " + ", ".join(bad[:5]),
                  bad)
