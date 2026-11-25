"""pmf_window.py — the PMF window, hand-coded in PySide6.

This is the scripted equivalent of ``pmf_pipeline.ui``: the same
window, built entirely in Python. No .ui file, no QUiLoader, no
``pyside6-uic`` step. It started as a conversion of the .ui
(69 widgets, same objectNames) and has moved on since: the Display
row was removed Nov 24, 2026, and the Model tab was redesigned
the same day from Sean's Qt Designer draft (fewer text boxes, one
Asset Notes box, Mesh / Rig / Skin import rows).

Why scripted, not Qt Designer (Sean's call, Nov 23, 2026):
  * You can read, review, diff, and merge it like any other code.
    A .ui file is XML; its diffs are noise and its merge conflicts
    are painful in a team.
  * It proves you understand Qt, not just that you can drag widgets:
    layouts, size policies, signals/slots, model/view lists,
    parenting a window into Maya. That is what a Pipeline TD
    interviewer asks about.
  * It is one less build step and one less file to keep in sync.
    The .ui file stays in the repo as the layout prototype that
    this file was converted from — it is no longer loaded at runtime.

How to read this file:
  * ``build_ui(parent)`` builds the whole window and returns a
    namespace (``ui``) whose attributes are the widgets, named
    after the .ui file where they came from (``ui.validateButton``,
    ``ui.characterListWidget``, ...). ``main.py`` wires signals
    against those names, so the logic does not care whether the
    widgets came from Designer or from here. Widgets added after
    the conversion (the Mesh / Rig / Skin import rows, Nov 24,
    2026) follow the same naming pattern.
  * Every widget gets ``setObjectName()`` with its name, so
    ``findChild`` / Qt Designer-style lookup still works.
  * Layout pattern throughout: a widget holds a layout; a layout
    holds widgets or sub-layouts. Nothing is positioned by pixels
    — Qt lays it out from the nesting + size hints. That is the
    single most important Qt idea in this file.

Run standalone (layout preview, no Maya):
    python -m pmf_pipeline.main   # now uses this file by default
"""
from types import SimpleNamespace

try:
    from PySide6 import QtWidgets, QtGui, QtCore
except Exception:
    try:
        # Maya 2022 and earlier ship PySide2, not PySide6.
        from PySide2 import QtWidgets, QtGui, QtCore
    except Exception:  # imported outside Maya / without Qt
        QtWidgets = QtGui = QtCore = None


# ---------------------------------------------------------------- helpers
def _label(text="", bold=False, size=None):
    lbl = QtWidgets.QLabel(text)
    style = []
    if bold:
        style.append("font-weight: bold")
    if size:
        style.append(f"font-size: {size}px")
    if style:
        lbl.setStyleSheet("; ".join(style) + ";")
    return lbl


def _button(text):
    return QtWidgets.QPushButton(text)


def _link(text, name, ui):
    """Clickable text, not a button: a blue underlined link (One
    Dark Pro blue #61afef) that reads like text and behaves like a
    link. The href is the link's objectName; main.py connects
    linkActivated to the slot for it."""
    lbl = QtWidgets.QLabel(
        f'<a href="{name}" style="color:#61afef; '
        f'text-decoration: underline;">{text}</a>')
    lbl.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
    lbl.setOpenExternalLinks(False)
    return _named(lbl, name, ui)


def _lineedit(placeholder="", readonly=False):
    le = QtWidgets.QLineEdit()
    le.setPlaceholderText(placeholder)
    le.setReadOnly(readonly)
    return le


def _plaintext(placeholder="", max_height=None):
    te = QtWidgets.QPlainTextEdit()
    te.setPlaceholderText(placeholder)
    if max_height:
        te.setMaximumHeight(max_height)
    return te


def _folder_button(tooltip=""):
    """Small browse-folder button (the folder icon in Sean's draft).

    Uses Qt's standard directory-open icon, so it matches the
    platform. Falls back to "…" if no application/style exists yet.
    """
    btn = QtWidgets.QToolButton()
    try:
        style = QtWidgets.QApplication.instance().style()
        btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_DirOpenIcon))
    except Exception:
        btn.setText("…")
    btn.setToolTip(tooltip)
    return btn


def _thumb_label(text, w, h):
    lbl = QtWidgets.QLabel(text)
    lbl.setMinimumSize(w, h)
    lbl.setMaximumSize(w, h)
    lbl.setAlignment(QtCore.Qt.AlignCenter)
    lbl.setStyleSheet("border: 1px solid #666; background: #2b2b2b; color: #aaa;")
    return lbl


def _listwidget(icon_w, icon_h, grid_w, grid_h, tooltip=""):
    lw = QtWidgets.QListWidget()
    lw.setViewMode(QtWidgets.QListView.IconMode)
    lw.setIconSize(QtCore.QSize(icon_w, icon_h))
    lw.setGridSize(QtCore.QSize(grid_w, grid_h))
    lw.setMovement(QtWidgets.QListView.Static)
    lw.setResizeMode(QtWidgets.QListView.Adjust)
    if tooltip:
        lw.setToolTip(tooltip)
    return lw


def _named(widget, name, ui):
    widget.setObjectName(name)
    setattr(ui, name, widget)
    return widget


# ---------------------------------------------------------------- builder
def build_ui(parent):
    """Build the full PMF window into ``parent`` (a QWidget).

    Returns a namespace of widgets, named as in pmf_pipeline.ui.
    The layouts are set on ``parent`` itself, so there is no extra
    container widget to add afterwards.
    """
    if QtWidgets is None:
        raise RuntimeError(
            "No Qt binding found — PySide6 (Maya 2023+) or PySide2 "
            "(Maya 2022 and earlier). Run this inside Maya.")
    ui = SimpleNamespace()
    parent.setWindowTitle("PMF — Project: Metal Fist | Character Pipeline")
    parent.resize(980, 760)

    main_layout = QtWidgets.QVBoxLayout(parent)
    _named(parent, "PMFMainWindow", ui)

    # -- header: title + project picker + root path -------------------
    # No "PMF" logo anymore (removed Nov 24, 2026): the whole title
    # is one bold line.
    header = QtWidgets.QHBoxLayout()
    header.addWidget(_named(_label("Project: Metal Fist Character Pipeline Tool",
                                    bold=True, size=14), "titleLabel", ui))
    header.addStretch(1)
    header.addWidget(_named(_label("Project:"), "projectLabel", ui))
    project_combo = _named(QtWidgets.QComboBox(), "projectCombo", ui)
    project_combo.addItems(["PMF", "Demo", "+ Add project…"])
    header.addWidget(project_combo)
    header.addWidget(_named(_lineedit("X:/Projects/PMF"), "projectRootLineEdit", ui))
    header.addWidget(_named(_button("Browse…"), "browseRootButton", ui))
    main_layout.addLayout(header)

    # -- main tab widget ------------------------------------------------
    tabs = _named(QtWidgets.QTabWidget(), "mainTabWidget", ui)
    main_layout.addWidget(tabs)

    _build_model_tab(tabs, ui)
    _build_animation_tab(tabs, ui)

    # -- status bar ------------------------------------------------------
    # The status bar starts empty (Nov 24, 2026 — Sean asked to
    # remove the "Ready — select a character..." line). It only
    # shows text when an action reports something: an import or
    # export result, an error, a missing preview.
    status = QtWidgets.QHBoxLayout()
    status.addWidget(_named(_label(""), "statusLabel", ui))
    main_layout.addLayout(status)
    return ui


# ---------------------------------------------------------------- Model tab
def _build_model_tab(tabs, ui):
    tab = _named(QtWidgets.QWidget(), "tabModel", ui)
    tabs.addTab(tab, "Model and Rig")
    layout = QtWidgets.QHBoxLayout(tab)

    # Left: character preview bar — a fixed 1x4 vertical column, not
    # resizable. One column, four rows: TopToBottom flow, no wrapping,
    # fixed width, uniform item sizes, square 128px icons. The four
    # thumbnails are square (150x150 / 200x200 from Drive), so every
    # icon renders at exactly the same size — no mismatched heights.
    chars = _named(
        _listwidget(128, 128, 140, 160,
                    "4 characters. Portrait = square thumbnail .png from "
                    "the asset folder. A '?' placeholder shows when a "
                    "character has no thumbnail yet."),
        "characterListWidget", ui)
    chars.setFlow(QtWidgets.QListView.TopToBottom)
    chars.setWrapping(False)
    chars.setUniformItemSizes(True)
    chars.setFixedWidth(148)
    chars.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
    layout.addWidget(chars)

    # Right: detail column — redesigned Nov 24, 2026 from Sean's
    # Qt Designer draft (pmf_pipeline_draft.ui): fewer text boxes,
    # one dedicated Asset Notes box, and three import rows
    # (Mesh / Rig / Skin) each with a browse-folder button. The
    # Description + Notes boxes and the Version + Textures lists
    # are gone — the mesh row shows the latest mesh file, the rig
    # row the rig to reference, the skin row the skin.json.
    # The left bar keeps the size of the current Maya UI (fixed
    # 1x4 column), not the big list in the draft.
    detail = QtWidgets.QVBoxLayout()

    # Top row, horizontal: preview image on the left; on the right,
    # the character name (larger), then File info, then Version
    # Notes. The preview is a full-body viewport shot, not the
    # square thumbnail — so the bar icon and the detail pane never
    # show the same image twice. (Layout changed Nov 24, 2026 at
    # Sean's request: File info + Asset Notes moved up beside
    # the preview, under the bigger title.)
    top_row = QtWidgets.QHBoxLayout()
    right = QtWidgets.QVBoxLayout()
    right.addWidget(_named(_label("Select a character", bold=True, size=18),
                           "modelNameLabel", ui))
    # File info group.
    file_group = _named(QtWidgets.QGroupBox("File info"),
                        "modelFileInfoGroup", ui)
    form = QtWidgets.QFormLayout(file_group)
    form.addRow(_named(_label("Namespace:"), "modelNamespaceLabel", ui),
                _named(_lineedit("CHAR01 — auto from character, never shared",
                                 readonly=True), "modelNamespaceLineEdit", ui))
    form.addRow(_named(_label("Last Modified:"), "modelModifiedLabel", ui),
                _named(_lineedit("—", readonly=True), "lastModifiedLineEdit", ui))
    right.addWidget(file_group)
    # Asset Notes — one dedicated box (was Description + Notes).
    # Fixed height, not just a maximum: QPlainTextEdit's sizeHint is
    # ~192px tall, which would inflate the whole top row's sizeHint.
    # Edit / Save / Cancel are clickable text on the right of the
    # "Asset Notes" heading — not a button — blue and underlined
    # so they read as clickable. Edit unlocks the box; Save writes
    # it to the repo's asset_notes.txt (see main._save_asset_notes)
    # and locks it again; Cancel discards the edits. Only Edit
    # shows until edit mode starts.
    notes_header = QtWidgets.QHBoxLayout()
    notes_header.addWidget(_named(_label("Asset Notes"), "versionNotesLabel", ui))
    notes_header.addStretch(1)
    notes_header.addWidget(_link("Edit", "assetNotesEditLink", ui))
    save_link = _link("Save", "assetNotesSaveLink", ui)
    save_link.hide()
    notes_header.addWidget(save_link)
    cancel_link = _link("Cancel", "assetNotesCancelLink", ui)
    cancel_link.hide()
    notes_header.addWidget(cancel_link)
    right.addLayout(notes_header)
    notes = _named(_plaintext(
        "Updated mesh to include props, new face design. Textures still WIP",
        max_height=64), "versionNotesTextEdit", ui)
    notes.setFixedHeight(64)
    notes.setReadOnly(True)
    right.addWidget(notes)
    # The preview spans the full height of the right column: its top
    # lines up with the character name, its bottom with Version
    # Notes. Fixed width, vertically Ignored — the layout stretches
    # it to the row height (the right column), so no measurement code
    # is needed. (A build-time sizeHint is 0 for a parentless layout,
    # and measuring in __init__ reads un-laid-out geometry.)
    # Ignored, not Expanding, on purpose (bug found Nov 25, 2026):
    # _show_character crops the pixmap to the label's current size,
    # and a QLabel's sizeHint is its pixmap size (+ the 1px border),
    # so with Expanding the pixmap fed back into the layout — the
    # top row grew a few px on every character switch, stretching
    # the whole window. Ignored tells the layout to size the label
    # from the row instead, so the pixmap can never drive it.
    thumb = _named(_thumb_label("Preview", 180, 180),
                   "modelThumbLabel", ui)
    thumb.setMaximumHeight(16777215)
    thumb.setSizePolicy(QtWidgets.QSizePolicy.Fixed,
                        QtWidgets.QSizePolicy.Ignored)
    top_row.addWidget(thumb)
    top_row.addLayout(right, 1)
    detail.addLayout(top_row)

    # Versions — three import rows: Mesh / Rig / Skin. Each row shows
    # the resolved path (or "not found yet"), a browse-folder button
    # to pick a different file, and its Import button. A QFormLayout
    # puts every label in one column and every field in another, so
    # the path fields (and the buttons) start at the same x in all
    # three rows — separate HBoxLayouts drifted, because "Mesh:" is
    # wider than "Rig:".
    ver_group = _named(QtWidgets.QGroupBox("Versions"), "modelVersionGroup", ui)
    ver_layout = QtWidgets.QFormLayout(ver_group)
    for kind, label, path_name, browse_name, import_name, import_text in [
            ("mesh", "Mesh:", "meshPathLineEdit", "meshBrowseButton",
             "meshImportButton", "Import Character Mesh"),
            ("rig", "Rig:", "rigImportPathLineEdit", "rigBrowseButton",
             "rigImportButton", "Import Rig"),
            ("skin", "Skin:", "skinPathLineEdit", "skinBrowseButton",
             "skinImportButton", "Import Skin")]:
        row = QtWidgets.QHBoxLayout()
        row.addWidget(_named(_lineedit("", readonly=True), path_name, ui), 1)
        row.addWidget(_named(
            _folder_button(f"Browse for the {kind} file"), browse_name, ui))
        row.addWidget(_named(_button(import_text), import_name, ui))
        ver_layout.addRow(
            _named(_label(label, bold=True), f"{kind}ImportLabel", ui), row)
    detail.addWidget(ver_group)

    # Validation group — one outline only. The results box has no
    # frame of its own: with the theme, its border inside the group
    # box's border read as two nested outlines.
    val_group = _named(
        QtWidgets.QGroupBox("Validation"),
        "validationGroup", ui)
    val_layout = QtWidgets.QVBoxLayout(val_group)
    # Three columns, side by side: the validation log on the left
    # (widest — it's what you read after a run), the check list in
    # the middle, and the Validate / Repair buttons in a single
    # column on the right. The buttons stretch vertically to fill
    # the empty space. Filled in by main._populate_validation_checks.
    row = QtWidgets.QHBoxLayout()
    results = _named(QtWidgets.QTextEdit(), "validationResultsText", ui)
    results.setReadOnly(True)
    results.setFrameStyle(QtWidgets.QFrame.NoFrame)
    results.setPlaceholderText(
        "Run Validate: only the checked checks run. FAIL blocks the "
        "export, WARN doesn't. Repair fixes the checks it can, "
        "then re-runs them.")
    row.addWidget(results, 2)
    checks = _named(QtWidgets.QListWidget(), "validationChecksList", ui)
    row.addWidget(checks, 1)
    buttons = QtWidgets.QVBoxLayout()
    validate = _named(_button("Validate\n⚠️"), "validateButton", ui)
    validate.setSizePolicy(QtWidgets.QSizePolicy.Preferred,
                           QtWidgets.QSizePolicy.Expanding)
    buttons.addWidget(validate)
    repair = _named(_button("Repair\n🛠️"), "repairButton", ui)
    repair.setSizePolicy(QtWidgets.QSizePolicy.Preferred,
                         QtWidgets.QSizePolicy.Expanding)
    buttons.addWidget(repair)
    row.addLayout(buttons)
    val_layout.addLayout(row)
    # Validation takes the extra vertical space: it is the box the
    # user reads after every Validate run, so it grows with the
    # window while Versions keeps its content height.
    detail.addWidget(val_group, 1)

    # Export buttons. The old Open / Reference / Import / Validate
    # Mesh / Export FBX → Unity / Snapshot row is gone (Nov 24,
    # 2026): Validate lives in the Validation group now, and the
    # three exports are the Unity handoff. Export Mesh embeds the
    # materials (and their textures) in the FBX; Export Rig is the
    # skeleton + skinned mesh; Export Skin writes skin.json.
    buttons = QtWidgets.QHBoxLayout()
    for name, text in [
            ("exportMeshButton", "Export Mesh"),
            ("exportRigButton", "Export Rig"),
            ("exportSkinButton", "Export Skin")]:
        buttons.addWidget(_named(_button(text), name, ui))
    detail.addLayout(buttons)

    layout.addLayout(detail)
    return tab


# ---------------------------------------------------------------- Animation tab
def _build_animation_tab(tabs, ui):
    tab = _named(QtWidgets.QWidget(), "tabAnimation", ui)
    tabs.addTab(tab, "Animation")
    layout = QtWidgets.QVBoxLayout(tab)

    # Header: character + rig reference path (read-only, auto-filled).
    header = QtWidgets.QHBoxLayout()
    header.addWidget(_named(_label("Character:"), "animCharLabel", ui))
    combo = _named(QtWidgets.QComboBox(), "animCharacterCombo", ui)
    combo.setToolTip(
        "Switching character switches rig reference, namespace, and "
        "animation library. They are never mixed.")
    header.addWidget(combo)
    header.addWidget(_named(_label("Rig reference:"), "rigPathLabel", ui))
    header.addWidget(_named(_lineedit(
        "Auto-filled from characters.json — e.g. …/CHAR01/rig/CHAR01_rig_v0003.ma",
        readonly=True), "rigPathLineEdit", ui))
    header.addWidget(_named(_button("Reference Rig"), "referenceRigButton", ui))
    header.addWidget(_named(_button("Reload"), "reloadRigButton", ui))
    layout.addLayout(header)

    body = QtWidgets.QHBoxLayout()

    # Left: animation library — a single-column text list (5x1),
    # no thumbnails. The clips are the rows; the preview lives in
    # the detail on the right, not here.
    lib = _named(
        _listwidget(128, 96, 140, 140,
                    "Animation library for the selected character only. "
                    "Double-click to import clip onto the referenced rig."),
        "animLibraryList", ui)
    lib.setViewMode(QtWidgets.QListView.ListMode)
    # The _listwidget helper sets a 140x140 grid for the old icon
    # mode — in ListMode the grid still spaces the rows out (140px
    # apart), so clear it: rows stack at their 48px size hint.
    lib.setGridSize(QtCore.QSize())
    lib.setMinimumWidth(200)
    lib.setMaximumWidth(280)
    body.addWidget(lib)

    # Right: clip detail — one column, top to bottom: clip title,
    # thumbnail, Animation Notes, frame range, File info, actions.
    # (Was a two-column thumb row: thumbnail left, name + notes
    # right. The side-by-side heights never matched, which left
    # the big gaps under the notes box.)
    detail = QtWidgets.QVBoxLayout()
    detail.addWidget(_named(_label("Select an animation clip", bold=True, size=18),
                            "animNameLabel", ui))
    thumb_row = QtWidgets.QHBoxLayout()
    thumb_row.addWidget(_named(_thumb_label("Clip\nthumbnail", 320, 180),
                               "animThumbLabel", ui))
    thumb_row.addStretch(1)
    detail.addLayout(thumb_row)
    # Animation Notes — one box, not two (was Description + Notes).
    # Same pattern as Asset Notes on the Model and Rig tab: a
    # heading with Edit / Save / Cancel as clickable text on the
    # right, a fixed 64px box, read-only until Edit. One file per
    # clip in the repo (see main._save_anim_notes); the clip's
    # "note" field in characters.json is the starting text when
    # no notes file exists yet.
    notes_header = QtWidgets.QHBoxLayout()
    notes_header.addWidget(_named(_label("Animation Notes"), "animationNotesLabel", ui))
    notes_header.addStretch(1)
    notes_header.addWidget(_link("Edit", "animNotesEditLink", ui))
    save_link = _link("Save", "animNotesSaveLink", ui)
    save_link.hide()
    notes_header.addWidget(save_link)
    cancel_link = _link("Cancel", "animNotesCancelLink", ui)
    cancel_link.hide()
    notes_header.addWidget(cancel_link)
    detail.addLayout(notes_header)
    notes = _named(_plaintext(
        "Notes for this clip — timing, loops, root motion, what to fix.",
        max_height=64), "animationNotesTextEdit", ui)
    notes.setFixedHeight(64)
    notes.setReadOnly(True)
    detail.addWidget(notes)

    # Frame range + namespace.
    frame_row = QtWidgets.QHBoxLayout()
    frame_row.addWidget(_named(_label("Start frame:"), "frameStartLabel", ui))
    start_spin = _named(QtWidgets.QSpinBox(), "animStartFrameSpin", ui)
    start_spin.setMaximum(100000)
    frame_row.addWidget(start_spin)
    frame_row.addWidget(_named(_label("End frame:"), "frameEndLabel", ui))
    end_spin = _named(QtWidgets.QSpinBox(), "animEndFrameSpin", ui)
    end_spin.setMaximum(100000)
    end_spin.setValue(24)
    frame_row.addWidget(end_spin)
    frame_row.addWidget(_named(_label("Namespace:"), "animNamespaceLabel", ui))
    frame_row.addWidget(_named(_lineedit("CHAR01", readonly=True),
                               "animNamespaceLineEdit", ui))
    detail.addLayout(frame_row)

    # File info group — same shape as the Model and Rig tab's
    # ("File info", no suffix): the clip file, and Last Modified.
    # No Version list: a clip is one file, no version history is
    # tracked — the Model tab dropped its Version list for the
    # same reason.
    file_group = _named(QtWidgets.QGroupBox("File info"),
                        "animFileInfoGroup", ui)
    form = QtWidgets.QFormLayout(file_group)
    form.addRow(_named(_label("File:"), "animFileLabel", ui),
                _named(_lineedit(
                    "…/assets/characters/CHAR01/anim/jab_v0002.ma",
                    readonly=True), "animFilePathLineEdit", ui))
    form.addRow(_named(_label("Last Modified:"), "animModifiedLabel", ui),
                _named(_lineedit("—", readonly=True), "animLastModifiedLineEdit", ui))
    detail.addWidget(file_group)

    # Action buttons.
    buttons = QtWidgets.QHBoxLayout()
    for name, text in [
            ("importAnimButton", "Import Clip"),
            ("exportAnimButton", "Export Clip (.ma)"),
            ("exportFBXUnityButton", "Export FBX → Unity"),
            ("batchExportButton", "Batch Export All")]:
        buttons.addWidget(_named(_button(text), name, ui))
    detail.addLayout(buttons)

    body.addLayout(detail)
    layout.addLayout(body)
    return tab
