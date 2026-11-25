"""ngon.py — faces with more than 4 sides.

Unity triangulates on import, so an n-gon doesn't break the export
outright — but n-gons shade badly and hide modelling errors, so for
a game character the rule is quads/tris only. Reads the edge count
per face from polyInfo -faceToEdge ("FACE 12: 3 4 5 6 7").
"""
import re

try:
    import maya.cmds as cmds
except Exception:  # outside Maya — check() raises a clear error
    cmds = None

from ._common import result, shape_for

ID = "ngon"
NAME = "No n-gons"
DESCRIPTION = ("Faces with more than 4 sides. Unity triangulates on "
               "import, but n-gons shade badly — quads/tris only.")
SEVERITY = "fail"

_FACE_RE = re.compile(r"FACE\s+(\d+)\s*:\s*(.*)")


def _require_maya():
    if cmds is None:
        raise RuntimeError("ngon check needs Maya (maya.cmds not available)")


def check(mesh):
    """Validate one mesh transform. Returns a result dict."""
    _require_maya()
    shape = shape_for(cmds, mesh)
    if shape is None:
        return result(ID, NAME, SEVERITY, False,
                      f"No mesh shape under {mesh}")

    ngons = []
    for row in cmds.polyInfo(shape, faceToEdge=True) or []:
        m = _FACE_RE.match(str(row))
        if not m:
            continue
        edges = m.group(2).split()
        if len(edges) > 4:
            ngons.append(f"face {m.group(1)} ({len(edges)} sides)")
    passed = not ngons
    return result(ID, NAME, SEVERITY, passed,
                  "quads/tris only" if passed
                  else f"{len(ngons)} n-gon(s): " + ", ".join(ngons[:5]),
                  ngons)
