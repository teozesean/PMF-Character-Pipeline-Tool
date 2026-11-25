"""config.py — single source of truth for PMF characters and paths.

Reads characters.json next to pmf_pipeline.ui.
Nothing in here imports maya.cmds or Qt, so it can be unit-tested.
"""
import json
import os


def default_config_path():
    # pmf_pipeline/core/config.py -> ../../characters.json
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "characters.json"))


def local_config_path(config_path=None):
    """Per-machine overrides, next to characters.json: pmf_local.json.

    The repo's characters.json is shared (it is in GitHub) — but
    project_root is different on every machine (Sean's X:/Projects/PMF
    vs Dayniel's folder). The GUI's Browse button saves the root here,
    and this file is gitignored, so one machine's path never lands in
    the shared file or in someone else's clone.
    """
    path = config_path or default_config_path()
    here = os.path.dirname(os.path.abspath(path))
    return os.path.join(here, "pmf_local.json")


def load_config(path=None):
    path = path or default_config_path()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Per-machine overrides win over the shared file, when present.
    local_path = local_config_path(path)
    if os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as f:
            data.update(json.load(f))
    return data


def save_project_root(root, config_path=None):
    """Save the asset folder for THIS machine only (pmf_local.json).

    Returns the path written. characters.json is never touched for
    the root — it stays the shared default.
    """
    path = local_config_path(config_path)
    local = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            local = json.load(f)
    local["project_root"] = root
    with open(path, "w", encoding="utf-8") as f:
        json.dump(local, f, indent=2)
        f.write("\n")
    return path


def load_projects(config_path=None):
    """Named projects for this machine: {name: root}.

    Stored in pmf_local.json next to characters.json (gitignored),
    because every machine keeps its assets somewhere different.
    Returns {} when nothing was saved yet.
    """
    path = local_config_path(config_path)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("projects", {}) or {}


def save_project(name, root, config_path=None):
    """Save one named project for this machine (pmf_local.json).

    Returns the path written.
    """
    path = local_config_path(config_path)
    local = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            local = json.load(f)
    projects = local.get("projects", {}) or {}
    projects[name] = root
    local["projects"] = projects
    with open(path, "w", encoding="utf-8") as f:
        json.dump(local, f, indent=2)
        f.write("\n")
    return path


def get_character(config, code):
    for ch in config.get("characters", []):
        if ch["code"] == code:
            return ch
    raise KeyError(f"Unknown character code: {code}")


def resolve(config, rel_path):
    """Join a config-relative path onto project_root."""
    root = config.get("project_root", "")
    return os.path.normpath(os.path.join(root, rel_path))


def tool_root():
    """Folder holding characters.json / pmf_pipeline.ui — the tool folder.

    Used as a fallback for files that actually live with the tool
    (e.g. the saved Detective portrait) when project_root doesn't
    have them yet.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", ".."))


def character_dir(config, code):
    """The character's own folder under project_root, e.g. "Deckard".

    Derived from the rig path's first component — the rig path is
    the one field every character has, and it always starts with
    the folder. Folder renames (Nov 24, 2026) flow through here
    without touching the code or the namespace.
    """
    ch = get_character(config, code)
    return ch["rig_path"].split("/")[0]


def asset_notes_path_for(config, code):
    """Per-character notes file, in the tool repo:
    assets/characters/<Folder>/asset_notes.txt.

    This is the file the Asset Notes box saves to — it lives in
    the Git repo (a .txt, so it is committed and pushed with the
    tool), not in the Drive asset folder. The old
    version_notes.txt in the asset folder is still read as a
    fallback (see main._load_asset_notes), so notes written there
    before Nov 24, 2026 aren't lost; new saves always go here.
    """
    folder = character_dir(config, code)
    return os.path.normpath(os.path.join(
        tool_root(), "assets", "characters", folder, "asset_notes.txt"))


def version_notes_path_for(config, code):
    """Per-character notes file, in the asset folder: <Folder>/version_notes.txt.

    Shared with Dayniel through Drive. The GUI loads it when the
    character is selected and saves it when you switch character
    or close the window — only when the asset folder actually
    exists on this machine.
    """
    return resolve(config, os.path.join(character_dir(config, code), "version_notes.txt"))


def anim_notes_path_for(config, code, clip):
    """Per-clip notes file, in the tool repo:
    assets/characters/<Folder>/animation_notes/<Clip>.txt.

    The Animation Notes box saves here — the same pattern as
    Asset Notes (a .txt in the Git repo, committed and pushed
    with the tool), one file per clip, so a clip's notes travel
    with the tool and never depend on the Drive asset folder.
    """
    folder = character_dir(config, code)
    return os.path.normpath(os.path.join(
        tool_root(), "assets", "characters", folder,
        "animation_notes", f"{clip}.txt"))


def clip_for(config, code, clip):
    """One anim clip dict by name, or None when the character has
    no such clip. Clips live in the character's "anim_clips" list
    in characters.json (file, key_range, keys, maya, drive_link)."""
    ch = get_character(config, code)
    for c in ch.get("anim_clips", []):
        if c.get("clip") == clip:
            return c
    return None


def clip_file_path_for(config, code, clip):
    """Where a clip's .ma file lives under project_root:
    <Folder>/anim/<file>. The file may not be downloaded yet —
    callers show this path as a placeholder reference then."""
    ch = get_character(config, code)
    entry = clip_for(config, code, clip)
    if entry is None:
        return None
    return resolve(config, os.path.join(
        ch.get("anim_dir", os.path.join(character_dir(config, code), "anim")),
        entry["file"]))


def clip_thumb_path_for(config, code, clip):
    """The clip's preview image, under project_root:
    <Folder>/thumbnail/<Clip>_thumb.gif first (an animated GIF —
    a playblast exported as a GIF; the Animation tab plays it
    with QMovie), else <Folder>/thumbnail/<Clip>_thumb.png,
    else None. No GIF or PNG yet for any clip (Nov 25, 2026) —
    the tab shows the 'Clip thumbnail' placeholder until Sean
    renders one in Maya."""
    folder = character_dir(config, code)
    for name in (f"{clip}_thumb.gif", f"{clip}_thumb.png"):
        path = resolve(config, os.path.join(folder, "thumbnail", name))
        if os.path.exists(path):
            return path
    return None


def skin_path_for(config, code):
    """Conventional skin-weights file: <Folder>/skinweight/skin.json.

    No skin files exist in Drive yet (Nov 24, 2026) — the Skin row
    shows "No skin.json yet" until one is added or picked with
    Browse. The format (ngSkinTools export vs Maya weights) is
    still an open question; see README §11.
    """
    return resolve(config, os.path.join(character_dir(config, code), "skinweight", "skin.json"))


def rig_path_for(config, code):
    ch = get_character(config, code)
    return resolve(config, ch["rig_path"])


def namespace_for(config, code):
    return get_character(config, code)["namespace"]


def preview_path_for(config, code):
    """Detail-preview image for a character — the big image in the
    Model tab, different from the square thumbnail in the bar.

    Asset folder first (the path in the character's "preview" field,
    e.g. Deckard/Deckard_viewport.jpg — a full-body viewport shot).
    If that file doesn't exist, fall back to the copy saved with
    the tool, in assets/characters/<Folder>/preview_<Folder>.jpg
    (or .png). If the character has no "preview" field and no tool
    copy (Jacques, Ryo, Delilah), the caller falls back to the
    square portrait thumbnail instead.
    """
    ch = get_character(config, code)
    if ch.get("preview"):
        project_path = resolve(config, ch["preview"])
        if os.path.exists(project_path):
            return project_path
    folder = character_dir(config, code)
    for ext in (".jpg", ".png"):
        copy = os.path.normpath(os.path.join(
            tool_root(), "assets", "characters", folder,
            f"preview_{folder}{ext}"))
        if os.path.exists(copy):
            return copy
    return os.path.normpath(os.path.join(
        tool_root(), "assets", "characters", folder,
        f"preview_{folder}.jpg"))


def portrait_path_for(config, code):
    """Portrait .png for a character.

    Asset folder first (the real PMF folder, once project_root is
    set in the GUI — e.g. Deckard/thumbnail/Deckard_thumbnail.png).
    If that file doesn't exist, fall back to the square copy saved
    with the tool, in assets/characters/<Folder>/portrait_<Folder>.png.
    If neither exists (Delilah has no thumbnail yet), the caller
    shows the '?' placeholder — see placeholder_path().
    """
    ch = get_character(config, code)
    project_path = resolve(config, ch["portrait"])
    if os.path.exists(project_path):
        return project_path
    folder = ch["portrait"].split("/")[0]  # e.g. "Deckard"
    return os.path.normpath(os.path.join(
        tool_root(), "assets", "characters", folder,
        f"portrait_{folder}.png"))


def placeholder_path():
    """The 200x200 square '?' icon, used when no thumbnail is found
    anywhere (Delilah, until a thumbnail is added). Lives with the
    tool, not in the asset folder, so it always exists."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "ui", "placeholder_thumbnail.png"))
