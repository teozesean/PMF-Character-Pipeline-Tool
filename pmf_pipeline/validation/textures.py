"""textures.py — every texture the mesh uses actually exists.

Materials live inside the mesh file (.ma/.fbx) — they are not
separate files — but they point at texture image files (.png) in
the texture/ folder. If one of those files is missing (renamed,
moved, never downloaded from Drive), Unity imports a broken
material: the mesh shows up pink or untextured. This check reads
every file node in the scene and verifies its fileTextureName
exists on disk.

Assumption, stated plainly: one character per scene (true for PMF
— each rig file is one fighter), so scene-wide file nodes are
that character's textures. A mesh with no file nodes passes.
"""
import os

try:
    import maya.cmds as cmds
except Exception:  # outside Maya — check() raises a clear error
    cmds = None

from ._common import result, shape_for

ID = "textures"
NAME = "Textures exist"
DESCRIPTION = ("Every file texture the mesh's materials point at "
               "exists on disk. A missing texture means a broken "
               "material in Unity.")
SEVERITY = "fail"


def _require_maya():
    if cmds is None:
        raise RuntimeError("textures check needs Maya (maya.cmds not available)")


def check(mesh):
    """Validate one mesh transform. Returns a result dict."""
    _require_maya()
    if shape_for(cmds, mesh) is None:
        return result(ID, NAME, SEVERITY, False,
                      f"No mesh shape under {mesh}")

    missing = []
    found = 0
    for node in cmds.ls(type="file") or []:
        path = cmds.getAttr(f"{node}.fileTextureName")
        if not path:
            continue
        found += 1
        if not os.path.exists(path):
            missing.append(f"{node}: {path}")
    passed = not missing
    return result(ID, NAME, SEVERITY, passed,
                  "no textures referenced" if found == 0
                  else (f"{found} texture(s) found" if passed
                        else f"{len(missing)} missing: " + ", ".join(missing[:5])),
                  missing)
