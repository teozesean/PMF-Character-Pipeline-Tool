"""manifold.py — the gate: a closed, watertight mesh.

Non-manifold edges/vertices, lamina faces and open edges (holes)
all break the Unity import or the skinning, so this check FAILS
the export when any of them show up.
"""
try:
    import maya.cmds as cmds
except Exception:  # outside Maya — check() raises a clear error
    cmds = None

from ._common import result, shape_for

ID = "manifold"
NAME = "Manifold geometry"
DESCRIPTION = ("Non-manifold edges/vertices, lamina faces, open "
               "edges/holes. A closed, watertight mesh is the gate "
               "for Unity export.")
SEVERITY = "fail"


def _require_maya():
    if cmds is None:
        raise RuntimeError("manifold check needs Maya (maya.cmds not available)")


def check(mesh):
    """Validate one mesh transform. Returns a result dict."""
    _require_maya()
    shape = shape_for(cmds, mesh)
    if shape is None:
        return result(ID, NAME, SEVERITY, False,
                      f"No mesh shape under {mesh}")

    parts = []
    nodes = []
    nm_edges = cmds.polyInfo(shape, nonManifoldEdges=True) or []
    if nm_edges:
        parts.append(f"{len(nm_edges)} non-manifold edge(s)")
        nodes += nm_edges
    nm_verts = cmds.polyInfo(shape, nonManifoldVertices=True) or []
    if nm_verts:
        parts.append(f"{len(nm_verts)} non-manifold vertex/vertices")
        nodes += nm_verts
    lamina = cmds.polyInfo(shape, laminaFaces=True) or []
    if lamina:
        parts.append(f"{len(lamina)} lamina face(s)")
        nodes += lamina
    try:
        n_border = cmds.polyEvaluate(shape, borderEdge=True)
        if n_border:
            parts.append(f"{n_border} border edge(s)")
    except Exception as e:
        parts.append(f"open edges not checked: {e}")

    passed = not parts
    return result(ID, NAME, SEVERITY, passed,
                  "watertight" if passed else "; ".join(parts), nodes)
