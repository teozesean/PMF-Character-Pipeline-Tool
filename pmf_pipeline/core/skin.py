"""skin.py — read a skin-weights JSON file written by ngSkinTools2.

CORRECTION (Nov 25, 2026): the format this module used to validate
was the v1 API's (``ngSkinTools.importExport`` — JsonExporter /
JsonImporter, from the published API docs). That API does not exist
in ngSkinTools2 2.1.6 — Sean confirmed in Maya on Nov 25, 2026:
``from ngSkinTools.importExport import JsonImporter`` raises
``ModuleNotFoundError: No module named 'ngSkinTools2.importExport'``.
The real API lives in the plug-in's own scripts folder
(``C:\\ProgramData\\Autodesk\\ApplicationPlugins\\ngskintools2\\
Contents\\scripts\\ngSkinTools2\\api\\import_export.py``):

    from ngSkinTools2.api import import_export
    import_export.import_json(target_mesh_name, path)   # reads the file
    import_export.export_json(target_mesh_name, path)   # writes the file

There is no JsonImporter / JsonExporter / LayerData in v2, and the
JSON schema the v2 exporter writes is not documented anywhere this
module can see — so this module no longer asserts any schema. It
only checks that the file is readable JSON (so a corrupt file fails
fast with a plain-English error instead of a cryptic plug-in
error) and summarises the layer names when the file has a
``layers`` list. The v2 importer/exporter are the authority on
their own format; the actual import/export lives in
``maya_bridge.import_skin_weights`` / ``export_skin_weights``.
"""
import json


class SkinWeightsError(ValueError):
    """The file is not a usable skin-weights JSON."""


def parse_skin_json(contents):
    """Parse skin-weights JSON text.

    Returns a summary dict:
        {"layers": [layer names, in file order], "data": <parsed>}
    Layer names come from ``data["layers"]`` when it is a list of
    dicts with a "name" — anything else in the file is left alone,
    because the v2 schema is not documented here. Raises
    SkinWeightsError when the text is not valid JSON or not a JSON
    object.
    """
    try:
        data = json.loads(contents)
    except json.JSONDecodeError as e:
        raise SkinWeightsError(f"Not valid JSON: {e}")
    if not isinstance(data, dict):
        raise SkinWeightsError("Not a skin-weights file — top level is not a JSON object.")
    layers = data.get("layers")
    names = []
    if isinstance(layers, list):
        for layer in layers:
            if isinstance(layer, dict):
                names.append(str(layer.get("name", "?")))
    return {"layers": names, "data": data}


def load_skin_json(path):
    """Read a skin.json from disk and parse it. Returns parse_skin_json's summary."""
    try:
        with open(path, encoding="utf-8") as f:
            contents = f.read()
    except OSError as e:
        raise SkinWeightsError(f"Could not read {path}: {e}")
    return parse_skin_json(contents)


def describe(summary):
    """One-line human summary, for the status bar."""
    names = summary["layers"]
    if names:
        return f"{len(names)} layer(s) ({', '.join(names)})"
    keys = ", ".join(summary["data"].keys())
    return f"skin file (top-level keys: {keys})"
