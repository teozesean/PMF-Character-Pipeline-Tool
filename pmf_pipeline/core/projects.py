"""projects.py — set up a PMF project folder's structure.

A project folder is the asset root the GUI points at: it holds one
folder per character, and each character folder has the same six
sub-folders (see README §3 for the contract):

    <Character>/mesh/         mesh files (.fbx, .obj)
    <Character>/texture/      texture images (.png) — NOT materials:
                              materials live inside the mesh file
                              (.ma/.fbx) and point at these files
    <Character>/rig/          rig files (.ma — never renamed, the
                              anim files reference the old names)
    <Character>/skinweight/   skin.json (ngSkinTools export)
    <Character>/anim/         animation scenes (.ma)
    <Character>/thumbnail/    square thumbnail + viewport preview

Pure stdlib, no Maya, no Qt — unit-tested.
"""
import os

CHARACTER_SUBFOLDERS = ("mesh", "texture", "rig", "skinweight",
                        "anim", "thumbnail")


def character_names(config):
    """Display names of the characters in characters.json, in order."""
    return [ch.get("display_name") or ch["code"]
            for ch in config.get("characters", [])]


def create_project_structure(root, names):
    """Create the project folder structure under root.

    Creates root itself plus one folder per character name, each
    with the six sub-folders above. Existing folders are left
    alone (os.makedirs with exist_ok=True), so running this on a
    folder that already has characters in it only fills the gaps.
    Returns the list of folders created.
    """
    created = []
    os.makedirs(root, exist_ok=True)
    for name in names:
        for sub in CHARACTER_SUBFOLDERS:
            path = os.path.join(root, name, sub)
            if not os.path.exists(path):
                os.makedirs(path)
                created.append(path)
    return created
