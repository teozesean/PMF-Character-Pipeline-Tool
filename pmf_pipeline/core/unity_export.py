"""unity_export.py — FBX out of Maya, into Unity, with the same names
every time so your friend never has to re-wire the Unity side.

Model:  {CODE}_model.fbx  — mesh + skeleton, bind pose, no animation
Anim:   {CODE}_{CLIP}.fbx — animation only, baked on the rig controls,
        frame range from the Animation tab, same skeleton as the model

FBX settings are set explicitly here (not left at Maya defaults):
  - FBXExportSmoothingGroups, FBXExportTangents, FBXExportTriangulate
    off for the model (Unity triangulates on import), bake on for anims
  - Up axis Y, units cm (Maya default) — Unity imports cm as 0.01 scale
    if you keep cm; agree this once with your friend and do not change it
    per-clip.
"""
try:
    import maya.cmds as cmds
    import maya.mel as mel
except Exception:
    cmds = None
    mel = None


def _require_maya():
    if cmds is None:
        raise RuntimeError("unity_export needs Maya")


def export_fbx(out_path, start_frame=None, end_frame=None, animation_only=False,
               embed_media=False):
    """Export current selection (or whole scene if nothing selected) to FBX.

    embed_media embeds the texture files inside the FBX (FBXExport
    "Embed Media") — the Unity handoff for Export Mesh, so the
    materials arrive with their textures instead of pointing at
    files Dayniel may not have.
    """
    _require_maya()
    # Load the FBX plugin if needed
    if not cmds.pluginInfo("fbxmaya", query=True, loaded=True):
        cmds.loadPlugin("fbxmaya")

    mel.eval("FBXResetExport")
    mel.eval("FBXExportSmoothingGroups -v true")
    mel.eval("FBXExportTangents -v true")
    mel.eval("FBXExportTriangulate -v false")
    mel.eval("FBXExportEmbeddedTextures -v "
             + ("true" if embed_media else "false"))
    if animation_only and start_frame is not None and end_frame is not None:
        mel.eval("FBXExportBakeComplexAnimation -v true")
        mel.eval(f"FBXExportBakeComplexStart -v {int(start_frame)}")
        mel.eval(f"FBXExportBakeComplexEnd -v {int(end_frame)}")
    else:
        mel.eval("FBXExportBakeComplexAnimation -v false")
    mel.eval(f'FBXExport -f "{out_path}" -s')
    return out_path


def export_mesh_fbx(config, code):
    """Export the character's mesh (with materials embedded) as FBX.

    Selects the referenced rig's skinned mesh first, so the export
    is the mesh alone — not the whole scene — then exports to
    unity_export/<CODE>/<CODE>_model.fbx with the textures
    embedded (FBX "Embed Media"). The material definitions travel
    inside the FBX and point at the embedded textures, so Unity
    renders the character without the texture/ folder.
    """
    _require_maya()
    from .config import namespace_for
    from .maya_bridge import find_skinned_mesh
    namespace = namespace_for(config, code)
    mesh = find_skinned_mesh(namespace)
    if mesh:
        cmds.select([mesh])
    return export_fbx(model_export_path(config, code), embed_media=True)


def model_export_path(config, code):
    from .config import resolve
    # unity_export_root in characters.json is project-relative in use:
    # keep the path relative so resolve() joins it onto project_root.
    return resolve(config, f"unity_export/{code}/{code}_model.fbx")


def anim_export_path(config, code, clip):
    from .config import resolve
    return resolve(config, f"unity_export/{code}/{code}_{clip}.fbx")


def rig_export_path(config, code):
    """Unity character file: skeleton + skinned mesh, no animation."""
    from .config import resolve
    return resolve(config, f"unity_export/{code}/{code}_rig.fbx")


def export_rig_fbx(config, code):
    """Export the referenced rig (skeleton + skinned mesh) as FBX.

    The rig must already be referenced under its namespace. Selects
    the joints under the namespace plus the skinned mesh, then
    exports (no bake, no animation) to
    unity_export/<CODE>/<CODE>_rig.fbx — the file Unity retargets
    the animation clips onto. Export Mesh is the mesh alone, with
    materials embedded; Export Rig is the rigged character.
    """
    _require_maya()
    from .config import namespace_for
    from .maya_bridge import find_skinned_mesh
    namespace = namespace_for(config, code)
    joints = cmds.ls(f"{namespace}:*", type="joint") or []
    mesh = find_skinned_mesh(namespace)
    selection = list(joints) + ([mesh] if mesh else [])
    if not selection:
        raise RuntimeError(
            f"No joints or skinned mesh under namespace '{namespace}' — "
            "reference the rig first, then export it.")
    cmds.select(selection)
    return export_fbx(rig_export_path(config, code))
