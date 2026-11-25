"""assets.py — scan the on-disk project, find versions + textures + thumbs.

Folder contract (per character, never shared):
  assets/characters/{CODE}/
    portrait_{CODE}.png
    model/{CODE}_model_v0001.ma … v000N.ma
    rig/{CODE}_rig_v0001.ma …
    textures/*.png / *.tga / *.exr
    anim/{CLIP}_v0001.ma …  + {CLIP}_thumb.png
  unity_export/{CODE}/  — FBX output only, never edited in Maya

Version rule: v0000…v9999, latest = highest number. No parsing of
file contents here — that belongs in validator / maya_bridge.
"""
import os
import re

VERSION_RE = re.compile(r"_v(\d{4})\.(ma|mb|fbx)$", re.IGNORECASE)
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tga", ".tif", ".tiff", ".exr"}


def latest_mesh_file(folders):
    """The mesh file to import for a character, or None.

    Scans the given folders (model_dir first, then the anim/source
    folder) for standalone mesh files. .fbx wins over .obj — the
    FBX is the Unity model — and within one extension the newest
    file wins. .ma/.mb scenes are NOT meshes: a rig-edit scene in
    the Model folder (e.g. Jacques_Rig_Edit.ma) must not show up
    as the mesh to import.
    """
    candidates = []
    for folder in folders:
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            ext = os.path.splitext(name)[1].lower()
            if ext not in MESH_EXTS:
                continue
            path = os.path.join(folder, name)
            rank = 0 if ext == ".fbx" else 1
            candidates.append((rank, -os.path.getmtime(path), path))
    if not candidates:
        return None
    return sorted(candidates)[0][2]


MESH_EXTS = {".fbx", ".obj"}


def list_versions(folder, prefix=""):
    """Return [(version_int, filename, full_path)] sorted ascending."""
    out = []
    if not os.path.isdir(folder):
        return out
    for name in sorted(os.listdir(folder)):
        if prefix and not name.startswith(prefix):
            continue
        m = VERSION_RE.search(name)
        if m:
            out.append((int(m.group(1)), name, os.path.join(folder, name)))
    return sorted(out)


def latest_version(folder, prefix=""):
    versions = list_versions(folder, prefix)
    return versions[-1] if versions else None


def list_textures(folder):
    if not os.path.isdir(folder):
        return []
    return sorted(
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in IMAGE_EXTS
    )


def list_anim_clips(anim_dir):
    """Group anim .ma files by clip name: {'jab': [(ver, file, path), …]}."""
    clips = {}
    if not os.path.isdir(anim_dir):
        return clips
    for name in sorted(os.listdir(anim_dir)):
        m = re.match(r"(.+)_v(\d{4})\.(ma|mb)$", name, re.IGNORECASE)
        if not m:
            continue
        clip, ver = m.group(1), int(m.group(2))
        clips.setdefault(clip, []).append((ver, name, os.path.join(anim_dir, name)))
    for clip in clips:
        clips[clip] = sorted(clips[clip])
    return clips


def thumb_for_anim(anim_dir, clip):
    for ext in (".png", ".jpg"):
        p = os.path.join(anim_dir, f"{clip}_thumb{ext}")
        if os.path.exists(p):
            return p
    return None
