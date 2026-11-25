"""maya_bridge.py — all maya.cmds calls live here, nowhere else.

Rules:
  * One character = one namespace, always the character code (CHAR01…).
    Never reuse a namespace across characters, never let Maya auto-name
    it (e.g. CHAR01_1) without fixing it first.
  * Rig is always referenced, never imported — anim clips are imported
    onto the referenced rig.
  * Importing an anim clip: import the .ma, then retarget / copy keys
    onto {namespace}:controls. The clip file itself only holds animation
    curves on controls with the same names.
"""
try:
    import maya.cmds as cmds
except Exception:
    cmds = None


def _require_maya():
    if cmds is None:
        raise RuntimeError("maya_bridge needs Maya (maya.cmds not available)")


def ensure_namespace(namespace):
    """Return a clean namespace; rename the clash instead of accepting _1."""
    _require_maya()
    if cmds.namespace(exists=namespace):
        # Already in use — caller must decide: replace reference or pick
        # a new scene. Do not silently create CHAR01_1.
        raise RuntimeError(
            f"Namespace '{namespace}' already exists in this scene. "
            "Remove / replace the existing reference first.")
    cmds.namespace(add=namespace)
    return namespace


def reference_rig(rig_path, namespace):
    """Reference the character rig under its namespace. Returns ref node."""
    _require_maya()
    if not cmds.namespace(exists=namespace):
        cmds.namespace(add=namespace)
    ref = cmds.file(rig_path, reference=True, namespace=namespace,
                    returnNewNodes=False)
    # cmds.file(reference=True) returns the reference node name(s)
    nodes = cmds.ls(type="reference")
    return nodes[-1] if nodes else ref


def replace_rig_reference(old_ref_node, new_rig_path):
    """Replace Reference — same namespace, new version file."""
    _require_maya()
    cmds.file(new_rig_path, loadReference=old_ref_node)
    return old_ref_node


def import_file(path, namespace=None):
    """Import a .ma/.mb/.fbx. If namespace is given, import under it."""
    _require_maya()
    kwargs = {"i": True}
    if namespace:
        kwargs["namespace"] = namespace
    return cmds.file(path, **kwargs)


def open_file(path):
    _require_maya()
    return cmds.file(path, open=True, force=True)


def list_references():
    _require_maya()
    return cmds.file(query=True, reference=True) or []


def find_skinned_mesh(namespace):
    """The skinned mesh for a character: the geometry under its
    namespace that has a skinCluster. Returns None when the rig
    isn't referenced (or has no skinCluster) yet."""
    _require_maya()
    for cluster in cmds.ls(type="skinCluster") or []:
        for geo in cmds.skinCluster(cluster, q=True, g=True) or []:
            if geo.startswith(f"{namespace}:"):
                return geo
    return None


def _require_ngskintools():
    """Load the ngSkinTools plug-in (tried as both names) or raise.

    The plug-in must be loaded for its Python package to be
    importable — the v2 API lives in the plug-in's scripts folder
    (ngSkinTools2/api/import_export.py). The plug-in name is tried
    as both "ngSkinTools" and "ngSkinTools2" (unverified which one
    Maya 2023 reports — confirm once in the Script Editor with
    ``cmds.pluginInfo(q=True, listPlugins=True)``).
    """
    for name in ("ngSkinTools", "ngSkinTools2"):
        try:
            if cmds.pluginInfo(name, query=True, loaded=True):
                return name
        except Exception:
            continue
    for name in ("ngSkinTools", "ngSkinTools2"):
        try:
            cmds.loadPlugin(name)
            return name
        except Exception:
            continue
    raise RuntimeError(
        "ngSkinTools plug-in is not loaded and could not be loaded "
        "(tried 'ngSkinTools' and 'ngSkinTools2'). Install/enable "
        "ngSkinTools2 in Maya first — the rig requires it.")


def import_skin_weights(path, namespace):
    """Apply an ngSkinTools2 skin-weights JSON onto the referenced rig.

    Uses the v2 API (``ngSkinTools2.api.import_export.import_json``)
    — verified Nov 25, 2026 against the plug-in's own scripts
    folder; the v1 ``JsonImporter`` does not exist in ngSkinTools2
    2.1.6. The file is checked first (readable JSON, see
    core/skin.py — the v2 importer reads the file itself, so the
    tool only pre-checks it is not corrupt). The mesh must already
    be skinned — the weights go onto the namespaced mesh of the
    referenced rig (e.g. ``Detective:MOD_Detective_Mesh``), not a
    bare imported mesh. ``import_json`` takes the mesh NAME and the
    file PATH (it loads the file itself); existing layers, if any,
    are preserved. Returns (mesh, summary) where summary is
    core/skin.py's parse result.

    The ngSkinTools plug-in must be loaded; the plug-in name is
    tried as both "ngSkinTools" and "ngSkinTools2" (unverified which
    one Maya 2023 reports — confirm once in the Script Editor with
    ``cmds.pluginInfo(q=True, listPlugins=True)``).
    """
    _require_maya()
    from .skin import load_skin_json, describe
    summary = load_skin_json(path)
    mesh = find_skinned_mesh(namespace)
    if mesh is None:
        raise RuntimeError(
            f"No skinned mesh found under namespace '{namespace}' — "
            "reference the rig first, then import the skin.")
    _require_ngskintools()
    try:
        from ngSkinTools2.api import import_export
    except ImportError as e:
        raise RuntimeError(
            "Could not import ngSkinTools2.api.import_export "
            f"({e}). In ngSkinTools2 2.1.6 the skin API lives in "
            "ngSkinTools2/api/import_export.py — check the plug-in is "
            "enabled in Maya.")
    import_export.import_json(mesh, path)
    return mesh, describe(summary)


def export_skin_weights(path, namespace):
    """Write the referenced rig's skin weights to a skin.json.

    The mirror of import_skin_weights: the v2 API
    (``ngSkinTools2.api.import_export.export_json``) writes the
    file itself from the namespaced skinned mesh (e.g.
    ``Detective:MOD_Detective_Mesh``) to path (conventionally
    ``<Character>/skinweight/skin.json``). The rig must already be
    referenced and the mesh skinned. Returns (mesh, summary) where
    summary is core/skin.py's parse of the file just written — the
    export validates its own output (readable JSON). Same v2
    note as the import: there is no JsonExporter / LayerData in
    ngSkinTools2 2.1.6.
    """
    _require_maya()
    from .skin import load_skin_json, describe
    mesh = find_skinned_mesh(namespace)
    if mesh is None:
        raise RuntimeError(
            f"No skinned mesh found under namespace '{namespace}' — "
            "reference the rig first, then export the skin.")
    _require_ngskintools()
    try:
        from ngSkinTools2.api import import_export
    except ImportError as e:
        raise RuntimeError(
            "Could not import ngSkinTools2.api.import_export "
            f"({e}). In ngSkinTools2 2.1.6 the skin API lives in "
            "ngSkinTools2/api/import_export.py — check the plug-in is "
            "enabled in Maya.")
    import_export.export_json(mesh, path)
    return mesh, describe(load_skin_json(path))


def controls_for(namespace):
    """Controls for a character: all transform nodes under its namespace
    whose name ends in _ctl / _ctrl.

    Verified Nov 23, 2026 on Detective_Rig_v08.ma: 157 _ctl + 48 _ctrl.
    In Deckard_HeavyKick.ma, 117 _ctl + 48 _ctrl are animated. Both
    suffixes are real — do not narrow this to one suffix.
    NOTE: a plain import of a Deckard_*.ma anim file duplicates the
    rig + mesh (it is a full scene, not clip-only). Import Clip must
    copy keys onto the referenced rig's controls instead — see
    DETECTIVE_INSPECTION.md."""
    _require_maya()
    nodes = cmds.ls(f"{namespace}:*", type="transform") or []
    return [n for n in nodes
            if n.split(":")[-1].endswith(("_ctl", "_ctrl", "_control"))]
