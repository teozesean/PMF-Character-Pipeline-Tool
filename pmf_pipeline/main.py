"""main.py — PMF window: hand-coded PySide6 UI in Maya (or standalone).

Run in Maya:
    import pmf_pipeline.main as pmf
    pmf.show()

Run standalone (layout preview only, no Maya calls):
    python -m pmf_pipeline.main

The UI is built in code by ``ui/pmf_window.py`` — the same window
and widget names the old Qt Designer .ui file had, now written as
Python. That is the source of truth for layout (Sean's call, Nov 23,
2026: scripted PySide6 is the Pipeline TD skill to build, and it
diffs/merges cleanly). ``pmf_pipeline.ui`` stays in the repo as the
layout prototype, and ``_load_ui`` still falls back to it if the
scripted module cannot be imported. Python only wires signals to
core/ functions — it never puts pipeline logic in the UI file.
"""
import os
import sys
import time

# False = build the UI from ui/pmf_window.py (default).
# True  = load pmf_pipeline.ui in Qt Designer / QUiLoader instead.
USE_DESIGNER_UI = False

try:
    from PySide6 import QtWidgets, QtGui, QtCore
    from PySide6.QtUiTools import QUiLoader
    from shiboken6 import wrapInstance as _wrapInstance
    QT_BINDING = "PySide6"
except Exception as _e6:
    try:
        # Maya 2022 and earlier ship PySide2, not PySide6.
        from PySide2 import QtWidgets, QtGui, QtCore
        from PySide2.QtUiTools import QUiLoader
        from shiboken2 import wrapInstance as _wrapInstance
        QT_BINDING = "PySide2"
    except Exception as _e2:
        QtWidgets = QtGui = QtCore = QUiLoader = None
        _wrapInstance = None
        QT_BINDING = None
        _qt_error = _e2

if QtWidgets is None:
    # Fail here, loudly, with the real cause — instead of dying later
    # with a cryptic "'NoneType' object has no attribute 'QWidget'"
    # at the PMFWindow class line when the Qt import silently failed.
    raise ImportError(
        "PMF: no Qt binding found — PySide6 (Maya 2023+) and PySide2 "
        "(Maya 2022 and earlier) both failed to import. Run this inside "
        f"Maya's Script Editor (Python tab), not a plain Python. Last error: {_qt_error}"
    )


def _ui_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "pmf_pipeline.ui"))


def _maya_main_window():
    try:
        import maya.OpenMayaUI as omui
        ptr = omui.MQtUtil.mainWindow()
        return _wrapInstance(int(ptr), QtWidgets.QWidget)
    except Exception:
        return None


class PMFWindow(QtWidgets.QWidget):
    def __init__(self, config=None, parent=None, config_path=None):
        super().__init__(parent)
        # Floating window, NOT an embedded panel. A QWidget parented
        # to Maya's main window without Qt.Window gets laid out *inside*
        # Maya: no title bar, no close button, can't be moved — it just
        # covers the viewport (seen Nov 23, 2026 on first launch in
        # Maya 2026). Qt.Window keeps the Maya parent (so it closes
        # with Maya and stays on top) while giving it its own frame.
        self.setWindowFlags(QtCore.Qt.Window)
        self.config = config  # dict from core.config.load_config()
        # Where this config came from — the GUI saves the project root
        # next to it (pmf_local.json), never into the shared file.
        self.config_path = config_path
        self.current_character = None
        # Whether the Asset Notes box has unsaved user edits. Only
        # the user typing (box editable) sets this — loading notes
        # does not — so switching character never writes a file
        # the user didn't touch.
        self._notes_dirty = False
        # The notes text as it was when Edit was pressed — Cancel
        # puts this back.
        self._notes_before_edit = ""
        # The selected anim clip (Animation tab), and the same
        # Edit/Save/Cancel state as Asset Notes, for Animation Notes.
        self.current_clip = None
        self._anim_notes_dirty = False
        self._anim_notes_before_edit = ""
        # The QMovie playing the current clip's GIF preview, or
        # None when the clip has no GIF.
        self._clip_movie = None
        # The missing-preview note last written to the status bar, or
        # "" when the last character had a preview. Switching to a
        # character with a preview clears it — otherwise Delilah's
        # "no preview ... showing the '?' placeholder" note would
        # stay under the next character (seen Nov 25, 2026). Only
        # cleared when the status still shows this note, so an
        # export/validation message is never wiped by a switch.
        self._portrait_note = ""
        # The project selected before "+ Add project…" was picked —
        # used to put the combo back if the Add flow is cancelled.
        self._previous_project = "PMF"
        # Browse picks for the Mesh / Rig / Skin rows, per character:
        # {code: {"mesh": path, "rig": path, "skin": path}}.
        # A pick wins over the resolved default until the character
        # is re-selected; it is not saved to disk (yet).
        self._import_paths = {}
        self._load_ui()
        self._apply_stylesheet()
        self._align_import_buttons()
        self._wire()
        self._populate_characters()
        self._populate_validation_checks()
        self._populate_projects()
        self._restore_geometry()

    def _settings(self):
        """Per-machine window settings (QSettings): geometry only.
        On macOS this lives in ~/Library/Preferences; on Windows
        in the registry; on Linux in ~/.config. Same idea as
        pmf_local.json, but Qt-owned, so it works standalone too."""
        return QtCore.QSettings("PMF", "CharacterPipelineTool")

    def _restore_geometry(self):
        """Re-open the window where it was: size + position from
        the last close. Gabriel Reed's Asset Browser did the same
        (artists asked for it); it matters most standalone, where
        the tool is opened fresh every day instead of living
        inside Maya."""
        geometry = self._settings().value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

    def _save_geometry(self):
        self._settings().setValue("geometry", self.saveGeometry())

    def _align_import_buttons(self):
        """The three Versions Import buttons have different text
        lengths — give them all the widest one's width, so the
        column lines up vertically across the rows.

        Runs after the stylesheet is applied, so sizeHint()
        reflects the styled padding: sizing at build time (before
        the theme) clipped "Import Character Mesh" to
        ":mport Character Mesh". Guards for the .ui fallback,
        which has no import rows.
        """
        names = ("meshImportButton", "rigImportButton", "skinImportButton")
        buttons = [getattr(self.ui, n, None) for n in names]
        buttons = [b for b in buttons if b is not None]
        if len(buttons) != 3:
            return
        widest = max(b.sizeHint().width() for b in buttons)
        for b in buttons:
            b.setFixedWidth(widest)

    def _load_ui(self):
        """Build the window. Scripted PySide6 first; .ui file as fallback.

        The scripted builder returns a namespace (``self.ui``) with
        the same attribute names the .ui loader used to produce, so
        ``_wire`` and the slots below are unchanged either way.
        """
        if not USE_DESIGNER_UI:
            try:
                from .ui.pmf_window import build_ui
                self.ui = build_ui(self)
                return
            except Exception as e:
                print(f"[PMF] scripted UI failed ({e}); falling back to .ui file.")
        loader = QUiLoader()
        ui_file = QtCore.QFile(_ui_path())
        ui_file.open(QtCore.QFile.ReadOnly)
        self.ui = loader.load(ui_file, self)
        ui_file.close()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.ui)
        self.setWindowTitle("PMF — Project: Metal Fist | Character Pipeline")

    def _apply_stylesheet(self):
        """Apply the One Dark Pro theme (QtVSCodeStyle), vendored with
        the tool so Maya needs no extra package installed.

        How it works: ``ui/qtvscode/onedark_pro.qss`` was generated
        once from OneDark-Pro.json by tools/generate_qtvscode_theme.py.
        Its icon URLs are the placeholder ``__QTVSCODE_SVG_DIR__``,
        which we swap here for the real ``ui/qtvscode/svg`` folder —
        so the theme works from any location, on any machine.

        Deliberately applied to *this window only* (setStyleSheet on
        the widget), NOT to the whole app: ``app.setStyleSheet(...)``
        inside Maya would restyle all of Maya's own UI too. In the
        standalone preview there is no Maya, so the window is the app.
        """
        here = os.path.dirname(os.path.abspath(__file__))
        qss_path = os.path.join(here, "ui", "qtvscode", "onedark_pro.qss")
        svg_dir = os.path.join(here, "ui", "qtvscode", "svg")
        try:
            with open(qss_path, encoding="utf-8") as f:
                qss = f.read()
        except OSError as e:
            print(f"[PMF] One Dark Pro stylesheet not found ({e}); "
                  "falling back to pmf_style.qss.")
            self._apply_fallback_stylesheet()
            return
        # QSS url() needs forward slashes even on Windows.
        qss = qss.replace("__QTVSCODE_SVG_DIR__", svg_dir.replace(os.sep, "/"))
        self.setStyleSheet(qss)
        print(f"[PMF] One Dark Pro stylesheet applied ({len(qss)} chars).")

    def _apply_fallback_stylesheet(self):
        """Sean's own dark starter (ui/pmf_style.qss) if the vendored
        theme file is missing. No-op if that is missing too."""
        here = os.path.dirname(os.path.abspath(__file__))
        qss_path = os.path.join(here, "ui", "pmf_style.qss")
        try:
            with open(qss_path, encoding="utf-8") as f:
                self.setStyleSheet(f.read())
            print("[PMF] Fallback stylesheet pmf_style.qss applied.")
        except OSError:
            print("[PMF] No stylesheet applied (neither theme file found).")

    # -- wiring: objectNames must match pmf_pipeline.ui --
    def _wire(self):
        u = self.ui
        # Refresh was removed Nov 24, 2026 at Sean's request — no
        # button in the header anymore. The refresh() slot is kept
        # for the .ui fallback path, so connect it only when present.
        if hasattr(u, "refreshButton"):
            u.refreshButton.clicked.connect(self.refresh)
        # Display controls (icons/list radios, filter box) were removed
        # from the scripted UI Nov 24, 2026 — the character bar is a
        # fixed 1x4 column now. They still exist in the .ui fallback
        # file, so connect them only when present; the slots are kept
        # for that path and otherwise do nothing.
        if hasattr(u, "searchLineEdit"):
            u.searchLineEdit.textChanged.connect(self._on_search)
        if hasattr(u, "viewIconsRadio"):
            u.viewIconsRadio.toggled.connect(self._on_view_mode)
        # Typing a path in the top-right field and pressing Enter
        # applies it exactly like Browse does.
        u.projectRootLineEdit.editingFinished.connect(
            lambda: self._apply_project_root(u.projectRootLineEdit.text()))
        if hasattr(u, "projectCombo"):
            u.projectCombo.currentTextChanged.connect(self._on_project_changed)
        u.characterListWidget.itemSelectionChanged.connect(self._on_character_selected)
        u.characterListWidget.itemDoubleClicked.connect(self._on_character_open)
        u.animCharacterCombo.currentTextChanged.connect(self._on_anim_character_changed)
        # The old Open / Reference / Import / Validate Mesh / Export
        # FBX → Unity / Snapshot row is gone from the scripted UI
        # (Nov 24, 2026) — Validate lives in the Validation group and
        # the row is Export Mesh / Rig / Skin. The old buttons still
        # exist in the .ui fallback file, so connect them only when
        # present; the slots are kept for that path.
        if hasattr(u, "openModelButton"):
            u.openModelButton.clicked.connect(lambda: self._model_action("open"))
        if hasattr(u, "referenceModelButton"):
            u.referenceModelButton.clicked.connect(lambda: self._model_action("reference"))
        if hasattr(u, "importModelButton"):
            u.importModelButton.clicked.connect(lambda: self._model_action("import"))
        if hasattr(u, "exportModelButton"):
            u.exportModelButton.clicked.connect(self._on_export_model)
        if hasattr(u, "snapshotModelButton"):
            u.snapshotModelButton.clicked.connect(self._on_snapshot)
        if hasattr(u, "validateButton"):
            u.validateButton.clicked.connect(self._on_validate)
        if hasattr(u, "repairButton"):
            u.repairButton.clicked.connect(self._on_repair)
        self._connect_if_present("exportMeshButton", self._on_export_mesh)
        self._connect_if_present("exportRigButton", self._on_export_rig)
        self._connect_if_present("exportSkinButton", self._on_export_skin)
        # Asset Notes actions are clickable text links, not buttons
        # (Nov 24, 2026): Edit / Save / Cancel, right of the
        # "Asset Notes" heading. linkActivated carries the href;
        # the slots don't need it.
        if hasattr(u, "assetNotesEditLink"):
            u.assetNotesEditLink.linkActivated.connect(
                lambda _href: self._on_asset_notes_edit())
        if hasattr(u, "assetNotesSaveLink"):
            u.assetNotesSaveLink.linkActivated.connect(
                lambda _href: self._on_asset_notes_save())
        if hasattr(u, "assetNotesCancelLink"):
            u.assetNotesCancelLink.linkActivated.connect(
                lambda _href: self._on_asset_notes_cancel())
        if hasattr(u, "versionNotesTextEdit"):
            u.versionNotesTextEdit.textChanged.connect(self._on_notes_changed)
        # Animation tab: clip selection, and Animation Notes links
        # (same Edit / Save / Cancel text-link pattern as Asset Notes).
        if hasattr(u, "animLibraryList"):
            u.animLibraryList.currentItemChanged.connect(self._on_clip_selected)
        if hasattr(u, "animNotesEditLink"):
            u.animNotesEditLink.linkActivated.connect(
                lambda _href: self._on_anim_notes_edit())
        if hasattr(u, "animNotesSaveLink"):
            u.animNotesSaveLink.linkActivated.connect(
                lambda _href: self._on_anim_notes_save())
        if hasattr(u, "animNotesCancelLink"):
            u.animNotesCancelLink.linkActivated.connect(
                lambda _href: self._on_anim_notes_cancel())
        if hasattr(u, "animationNotesTextEdit"):
            u.animationNotesTextEdit.textChanged.connect(self._on_anim_notes_changed)
        u.referenceRigButton.clicked.connect(self._on_reference_rig)
        u.reloadRigButton.clicked.connect(self._on_reference_rig)
        u.importAnimButton.clicked.connect(self._on_import_anim)
        u.exportAnimButton.clicked.connect(self._on_export_anim)
        u.exportFBXUnityButton.clicked.connect(self._on_export_anim_fbx)
        u.batchExportButton.clicked.connect(self._on_batch_export)
        u.browseRootButton.clicked.connect(self._on_browse_root)
        # Mesh / Rig / Skin import rows — scripted UI only (Nov 24,
        # 2026 redesign); the .ui fallback file doesn't have them.
        self._connect_if_present(
            "meshBrowseButton", lambda: self._on_browse_import("mesh"))
        self._connect_if_present(
            "rigBrowseButton", lambda: self._on_browse_import("rig"))
        self._connect_if_present(
            "skinBrowseButton", lambda: self._on_browse_import("skin"))
        self._connect_if_present("meshImportButton", self._on_import_mesh)
        self._connect_if_present("rigImportButton", self._on_import_rig)
        self._connect_if_present("skinImportButton", self._on_import_skin)

    def _connect_if_present(self, name, slot):
        """Connect a signal only when the widget exists.

        The scripted UI has widgets the .ui fallback file doesn't
        (the import rows). Connecting blindly would crash the
        fallback path; skipping silently keeps it working.
        """
        widget = getattr(self.ui, name, None)
        if widget is not None:
            widget.clicked.connect(slot)

    def _populate_validation_checks(self):
        """Fill the Validation checklist from validation/.

        One row per check file (manifold.py, ngon.py, ...), checked
        by default, tooltip is the check's DESCRIPTION. The check
        ID rides in the item's UserRole data, so _on_validate can
        run only the checked ones. Guarded for the .ui fallback,
        which has no checklist.
        """
        u = self.ui
        if not hasattr(u, "validationChecksList"):
            return
        from .validation import discover_checks
        u.validationChecksList.clear()
        for module in discover_checks():
            item = QtWidgets.QListWidgetItem(module.NAME)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked)
            item.setToolTip(module.DESCRIPTION)
            item.setData(QtCore.Qt.UserRole, module.ID)
            u.validationChecksList.addItem(item)

    def _populate_projects(self):
        """Add this machine's saved projects to the dropdown.

        Saved projects live in pmf_local.json (see core.config);
        they are inserted before the "+ Add project…" item. PMF
        stays selected — this only fills the list.
        """
        u = self.ui
        if not hasattr(u, "projectCombo"):
            return
        from .core.config import load_projects
        combo = u.projectCombo
        add_index = combo.findText("+ Add project…")
        if add_index < 0:
            add_index = combo.count()
        for name in load_projects(self.config_path):
            if combo.findText(name) < 0:
                combo.insertItem(add_index, name)
                add_index += 1

    def _on_project_changed(self, text):
        """The project dropdown.

        "+ Add project…" starts the setup flow (name + folder, then
        the folder structure is created). A saved project switches
        the asset root to that project's folder. PMF / Demo have no
        saved root, so they leave the current root alone.
        """
        if text == "+ Add project…":
            self._add_project()
            return
        self._previous_project = text
        if self.config is None:
            return
        from .core.config import load_projects
        root = load_projects(self.config_path).get(text)
        if root and os.path.isdir(root):
            self._apply_project_root(root)

    def _add_project(self):
        """Set up a new project's folder structure (Add + flow).

        Asks for a name and a folder, creates the per-character
        mesh / texture / rig / skinweight / anim / thumbnail
        structure under it (core.projects), saves the project for
        this machine (pmf_local.json), and switches the tool to
        that folder. Cancelling puts the dropdown back where it was.
        """
        combo = self.ui.projectCombo

        def _revert():
            combo.setCurrentText(self._previous_project or "PMF")

        name, ok = QtWidgets.QInputDialog.getText(
            self, "Add project", "Project name:")
        if not ok or not (name or "").strip():
            _revert()
            return
        name = name.strip()
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, f"Choose the folder for {name}")
        if not folder:
            _revert()
            return
        from .core.config import save_project
        from .core.projects import character_names, create_project_structure
        created = create_project_structure(
            folder, character_names(self.config or {}))
        save_project(name, folder, self.config_path)
        add_index = combo.findText("+ Add project…")
        if add_index < 0:
            add_index = combo.count()
        combo.insertItem(add_index, name)
        combo.setCurrentText(name)
        self._apply_project_root(folder)
        self._set_status(
            f"Project {name}: created {len(created)} folder(s) under {folder}.")

    def _populate_characters(self):
        if not self.config:
            return
        u = self.ui
        u.animCharacterCombo.clear()
        u.characterListWidget.clear()
        from .core.config import placeholder_path
        placeholder = placeholder_path()
        for ch in self.config.get("characters", []):
            u.animCharacterCombo.addItem(ch["display_name"], ch["code"])
            item = QtWidgets.QListWidgetItem(ch["display_name"])
            # Portrait: square thumbnail .png from the asset folder,
            # or the square copy saved with the tool. No thumbnail
            # anywhere (Delilah) -> the 200x200 '?' placeholder icon.
            from .core.config import portrait_path_for
            portrait = portrait_path_for(self.config, ch["code"])
            if os.path.exists(portrait):
                item.setIcon(QtGui.QIcon(portrait))
            elif os.path.exists(placeholder):
                item.setIcon(QtGui.QIcon(placeholder))
            item.setData(QtCore.Qt.UserRole, ch["code"])
            u.characterListWidget.addItem(item)
        # The window grows with the character bar: every character
        # visible, no scrolling (4 characters, for now). The bar's
        # minimum height is its full content height — rows × grid
        # height + frame — so the layout makes the window tall
        # enough instead of letting the list scroll and cut the
        # last character off. If a 5th character is added, the bar
        # grows with it.
        bar = u.characterListWidget
        bar.setMinimumHeight(
            bar.count() * bar.gridSize().height()
            + 2 * bar.frameWidth())
        if self.config.get("project_root"):
            u.projectRootLineEdit.setText(self.config["project_root"])

    # -- slots: thin wrappers, real work is in core/ --
    def refresh(self):
        self._save_asset_notes()
        self._save_anim_notes()
        self._populate_characters()
        self._set_status("Refreshed from characters.json + disk scan.")

    def _on_search(self, text):
        needle = text.strip().lower()
        for i in range(self.ui.characterListWidget.count()):
            item = self.ui.characterListWidget.item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def _on_view_mode(self, _checked):
        icons = self.ui.viewIconsRadio.isChecked()
        mode = (QtWidgets.QListView.IconMode if icons
                else QtWidgets.QListView.ListMode)
        self.ui.characterListWidget.setViewMode(mode)
        self.ui.animLibraryList.setViewMode(mode)

    def _on_character_selected(self):
        items = self.ui.characterListWidget.selectedItems()
        if not items:
            return
        code = items[0].data(QtCore.Qt.UserRole)
        if code != self.current_character:
            self._save_asset_notes()
            self._save_anim_notes()
        self.current_character = code
        self._show_character(code)

    def _show_character(self, code):
        from .core.config import get_character, rig_path_for
        ch = get_character(self.config, code)
        u = self.ui
        u.modelNameLabel.setText(ch["display_name"])
        u.modelNamespaceLineEdit.setText(ch["namespace"])
        u.animNamespaceLineEdit.setText(ch["namespace"])
        u.rigPathLineEdit.setText(rig_path_for(self.config, code))
        # Sync the Animation tab combo to the same character
        idx = u.animCharacterCombo.findData(code)
        if idx >= 0:
            u.animCharacterCombo.setCurrentIndex(idx)
        # Detail preview — the big image beside the name. A preview
        # image when the character has one (Deckard's full-body
        # viewport shot), else the square thumbnail, else the '?'
        # placeholder. The bar icon and the detail pane never show
        # the same image twice when a preview exists.
        from .core.config import (portrait_path_for, placeholder_path,
                                  preview_path_for)
        preview = preview_path_for(self.config, code)
        portrait = portrait_path_for(self.config, code)
        portrait_note = ""
        if os.path.exists(preview):
            shown = preview
        elif os.path.exists(portrait):
            shown = portrait
        else:
            shown = placeholder_path()
        if os.path.exists(shown):
            # Fill the label exactly (its height spans the name down
            # to Asset Notes): scale to cover, then centre-crop.
            # A plain aspect-fit would leave gaps top and bottom.
            size = u.modelThumbLabel.size()
            if size.width() <= 0 or size.height() <= 0:
                size = QtCore.QSize(180, 180)
            scaled = QtGui.QPixmap(shown).scaled(
                size, QtCore.Qt.KeepAspectRatioByExpanding,
                QtCore.Qt.SmoothTransformation)
            x = max(0, (scaled.width() - size.width()) // 2)
            y = max(0, (scaled.height() - size.height()) // 2)
            u.modelThumbLabel.setPixmap(
                scaled.copy(x, y, size.width(), size.height()))
            if not os.path.exists(preview) and not os.path.exists(portrait):
                portrait_note = (f" — no preview or thumbnail found at {preview}; "
                                 "showing the '?' placeholder.")
        else:
            # Never fail silently here: the old code just left the
            # "Portrait .png" placeholder, with no clue where it looked.
            u.modelThumbLabel.setText("Preview\nnot found")
            portrait_note = (f" — preview not found at {preview} "
                             "(set project_root in the top-right field).")
        # New in the Nov 24, 2026 redesign: File info date, Version
        # Notes, and the Mesh / Rig / Skin rows. The .ui fallback
        # doesn't have these widgets, so guard each one.
        if hasattr(u, "lastModifiedLineEdit"):
            u.lastModifiedLineEdit.setText(self._last_modified_text(code))
        if hasattr(u, "versionNotesTextEdit"):
            u.versionNotesTextEdit.setPlainText(self._load_asset_notes(code))
            # Switching character always locks the notes again: the
            # new character's notes start read-only, "Edit" to change.
            u.versionNotesTextEdit.setReadOnly(True)
            self._notes_dirty = False
            self._set_notes_links(editing=False)
        if hasattr(u, "meshPathLineEdit"):
            self._set_row("mesh", self._row_path("mesh", code))
            self._set_row("rig", self._row_path("rig", code))
            self._set_row("skin", self._row_path("skin", code))
        # The status bar is for action feedback, not a per-character
        # reminder — the "Selected DETECTIVE — rig, textures and
        # anims are DETECTIVE-only" line was removed Nov 24, 2026.
        # Only a missing-preview note still shows, and only when
        # there is one. When there isn't one, clear the previous
        # character's note — but only if the status still shows
        # that note, so a switch never wipes an export or
        # validation message.
        if portrait_note:
            self._portrait_note = portrait_note.lstrip(" —")
            self._set_status(self._portrait_note)
        elif (self._portrait_note
                and self.ui.statusLabel.text() == self._portrait_note):
            self._portrait_note = ""
            self._set_status("")
        # Animation tab: the library follows the character.
        if hasattr(u, "animLibraryList"):
            self._populate_anim_library(code)

    def _on_character_open(self, item):
        self._model_action("open")

    def _on_anim_character_changed(self, _text):
        code = self.ui.animCharacterCombo.currentData()
        if code:
            if code != self.current_character:
                self._save_asset_notes()
                self._save_anim_notes()
            self.current_character = code
            self._show_character(code)

    # -- Animation library + clip detail -----------------------------
    def _populate_anim_library(self, code):
        """Fill the Animation tab's library with the character's
        clips (from characters.json anim_clips — file, key_range,
        keys, maya, drive_link). The .ma files may not be
        downloaded yet; the library is the placeholder reference
        to them, and _show_clip shows the local path when the file
        exists, else the relative anim/ path. Characters with no
        clips get an empty library and a cleared detail."""
        u = self.ui
        if not hasattr(u, "animLibraryList"):
            return
        from .core.config import get_character
        ch = get_character(self.config, code)
        clips = ch.get("anim_clips", [])
        lib = u.animLibraryList
        lib.clear()
        for clip in clips:
            # Two lines: bold clip name, then the full .ma filename
            # as a subtitle. The subtitle is what makes versions
            # readable later (Deckard_Dashing_v002.ma vs v001) —
            # the title stays the clip name. Rows are 48px tall and
            # packed from the top, so the bottom of the list stays
            # empty for clips added later. A setItemWidget is used
            # because QListWidget does not render HTML in item text
            # (verified Nov 25, 2026 — the tags showed as literal
            # text, plain Qt and themed alike). The row is
            # transparent so the selection highlight shows through.
            # The row widget draws the text — the item's own text
            # stays empty, or the delegate draws it too, on top of
            # the widget. The name lives in UserRole.
            item = QtWidgets.QListWidgetItem()
            item.setData(QtCore.Qt.UserRole, clip["clip"])
            item.setSizeHint(QtCore.QSize(0, 48))
            keys = clip.get("keys")
            keys_text = f"{keys:,} keys" if isinstance(keys, int) else ""
            item.setToolTip(
                f"{keys_text}, "
                f"frames {clip['key_range'][0]}–{clip['key_range'][1]}, "
                f"Maya {clip['maya']}")
            lib.addItem(item)
            row = QtWidgets.QWidget()
            row.setStyleSheet("background: transparent;")
            row_layout = QtWidgets.QVBoxLayout(row)
            row_layout.setContentsMargins(6, 4, 6, 4)
            row_layout.setSpacing(0)
            title = QtWidgets.QLabel(f"<b>{clip['clip']}</b>")
            title.setStyleSheet("background: transparent;")
            subtitle = QtWidgets.QLabel(clip["file"])
            subtitle.setStyleSheet(
                "background: transparent; color: #9da5b4; font-size: 12px;")
            row_layout.addWidget(title)
            row_layout.addWidget(subtitle)
            lib.setItemWidget(item, row)
        if clips:
            lib.setCurrentRow(0)
        else:
            self.current_clip = None
            self._clear_clip_detail()

    def _on_clip_selected(self, current, _previous=None):
        if current is None:
            return
        clip = current.data(QtCore.Qt.UserRole)
        if not clip:
            return
        if clip != self.current_clip:
            self._save_anim_notes()
        self.current_clip = clip
        self._show_clip(clip)

    def _show_clip(self, clip):
        """Fill the Animation tab detail for one clip: name, frame
        range (the parsed key range, not playback), file reference,
        Last Modified, and Animation Notes. The .ui fallback
        doesn't have these widgets, so each one is guarded."""
        from .core.config import (clip_for, clip_file_path_for,
                                  character_dir)
        code = self.current_character
        entry = clip_for(self.config, code, clip)
        if entry is None:
            self._clear_clip_detail()
            return
        u = self.ui
        if hasattr(u, "animNameLabel"):
            u.animNameLabel.setText(entry["clip"])
        start, end = entry.get("key_range", [0, 24])
        if hasattr(u, "animStartFrameSpin"):
            u.animStartFrameSpin.setValue(start)
        if hasattr(u, "animEndFrameSpin"):
            u.animEndFrameSpin.setValue(end)
        path = clip_file_path_for(self.config, code, clip)
        if hasattr(u, "animFilePathLineEdit"):
            if path and os.path.exists(path):
                u.animFilePathLineEdit.setText(path)
            else:
                # Placeholder reference: the file isn't downloaded
                # yet, so the relative anim/ path is the reference.
                folder = character_dir(self.config, code)
                u.animFilePathLineEdit.setText(
                    os.path.join(folder, "anim", entry["file"]))
            if entry.get("drive_link"):
                u.animFilePathLineEdit.setToolTip(
                    f"Drive: {entry['drive_link']}")
        if hasattr(u, "animLastModifiedLineEdit"):
            u.animLastModifiedLineEdit.setText(
                self._clip_last_modified_text(code, clip))
        if hasattr(u, "animationNotesTextEdit"):
            u.animationNotesTextEdit.setPlainText(
                self._load_anim_notes(code, clip))
            u.animationNotesTextEdit.setReadOnly(True)
            self._anim_notes_dirty = False
            self._set_anim_notes_links(editing=False)
        self._show_clip_thumb(code, clip)

    def _show_clip_thumb(self, code, clip):
        """The clip preview under the title: an animated GIF when
        one exists (<Folder>/thumbnail/<Clip>_thumb.gif — a
        playblast exported as a GIF), played with QMovie and scaled
        to the thumbnail label; else the static
        <Clip>_thumb.png; else the 'Clip thumbnail' placeholder.
        The previous clip's movie is always stopped first, so a
        GIF never keeps playing after its clip is gone."""
        from .core.config import clip_thumb_path_for
        u = self.ui
        if not hasattr(u, "animThumbLabel"):
            return
        label = u.animThumbLabel
        if self._clip_movie is not None:
            self._clip_movie.stop()
            self._clip_movie = None
            label.setMovie(None)
        path = clip_thumb_path_for(self.config, code, clip)
        if path and path.lower().endswith(".gif"):
            movie = QtGui.QMovie(path)
            movie.setScaledSize(label.size())
            label.setMovie(movie)
            movie.start()
            self._clip_movie = movie
        elif path:
            label.setPixmap(QtGui.QPixmap(path).scaled(
                label.size(), QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation))
        else:
            label.setPixmap(QtGui.QPixmap())
            label.setText("Clip\nthumbnail")

    def _clear_clip_detail(self):
        """Empty the Animation tab detail: no clips for this
        character, so nothing is selected."""
        u = self.ui
        if hasattr(u, "animNameLabel"):
            u.animNameLabel.setText("Select an animation clip")
        if hasattr(u, "animStartFrameSpin"):
            u.animStartFrameSpin.setValue(0)
        if hasattr(u, "animEndFrameSpin"):
            u.animEndFrameSpin.setValue(24)
        if hasattr(u, "animFilePathLineEdit"):
            u.animFilePathLineEdit.setText("")
            u.animFilePathLineEdit.setPlaceholderText(
                "No anim files for this character yet")
            u.animFilePathLineEdit.setToolTip("")
        if hasattr(u, "animLastModifiedLineEdit"):
            u.animLastModifiedLineEdit.setText("—")
        if hasattr(u, "animationNotesTextEdit"):
            u.animationNotesTextEdit.setPlainText("")
            u.animationNotesTextEdit.setReadOnly(True)
            self._anim_notes_dirty = False
            self._set_anim_notes_links(editing=False)
        if hasattr(u, "animThumbLabel"):
            if self._clip_movie is not None:
                self._clip_movie.stop()
                self._clip_movie = None
                u.animThumbLabel.setMovie(None)
            u.animThumbLabel.setPixmap(QtGui.QPixmap())
            u.animThumbLabel.setText("Clip\nthumbnail")

    def _clip_last_modified_text(self, code, clip):
        """One date for the Animation tab's File info: the clip
        file's mtime when downloaded, else the modified date
        recorded for it in characters.json (the Drive date), else "—"."""
        from .core.config import clip_for, clip_file_path_for
        path = clip_file_path_for(self.config, code, clip)
        if path and os.path.exists(path):
            return time.strftime("%m/%d/%Y %H:%M",
                                 time.localtime(os.path.getmtime(path)))
        entry = clip_for(self.config, code, clip)
        if entry and entry.get("modified"):
            return entry["modified"]
        return "—"

    # -- Asset Notes -------------------------------------------------
    def _load_asset_notes(self, code):
        """Notes text for a character.

        The repo's assets/characters/<Folder>/asset_notes.txt wins
        when it exists; otherwise the old <Folder>/version_notes.txt
        in the asset folder (Drive) is read, so notes written there
        before Nov 24, 2026 aren't lost. "" when neither exists.
        """
        from .core.config import asset_notes_path_for, version_notes_path_for
        for path in (asset_notes_path_for(self.config, code),
                     version_notes_path_for(self.config, code)):
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    return f.read()
        return ""

    def _save_asset_notes(self):
        """Save the Asset Notes box for the current character.

        Written to assets/characters/<Folder>/asset_notes.txt in
        the tool repo — a .txt, so it is committed and pushed to
        Git with the tool. (The old version_notes.txt in the Drive
        asset folder is read-only fallback now; new saves never go
        there.) Called by the Save button, when switching
        character, and when the window closes.
        """
        code = self.current_character
        if not code or self.config is None:
            return
        if not hasattr(self.ui, "versionNotesTextEdit"):
            return
        if not self._notes_dirty:
            return  # nothing the user typed — don't touch the file
        from .core.config import asset_notes_path_for
        notes_path = asset_notes_path_for(self.config, code)
        text = self.ui.versionNotesTextEdit.toPlainText()
        try:
            existing = ""
            if os.path.exists(notes_path):
                with open(notes_path, encoding="utf-8") as f:
                    existing = f.read()
            if text != existing and (text or os.path.exists(notes_path)):
                os.makedirs(os.path.dirname(notes_path), exist_ok=True)
                with open(notes_path, "w", encoding="utf-8") as f:
                    f.write(text)
            self._notes_dirty = False
        except OSError as e:
            self._set_status(f"Could not save asset notes for {code}: {e}")

    def _on_notes_changed(self):
        """The Asset Notes box changed. Only the user typing counts:
        loading notes (setPlainText while read-only) must not mark
        the notes dirty, or switching character would write a file
        the user never touched."""
        if hasattr(self.ui, "versionNotesTextEdit") and \
                not self.ui.versionNotesTextEdit.isReadOnly():
            self._notes_dirty = True

    def _set_notes_links(self, editing):
        """Which Asset Notes links show: Edit alone in view mode,
        Save + Cancel in edit mode."""
        u = self.ui
        if hasattr(u, "assetNotesEditLink"):
            u.assetNotesEditLink.setVisible(not editing)
        if hasattr(u, "assetNotesSaveLink"):
            u.assetNotesSaveLink.setVisible(editing)
        if hasattr(u, "assetNotesCancelLink"):
            u.assetNotesCancelLink.setVisible(editing)

    def _on_asset_notes_edit(self):
        """The "Edit" link: unlock the box for typing, show Save +
        Cancel. The pre-edit text is remembered so Cancel can put
        it back."""
        u = self.ui
        if not hasattr(u, "versionNotesTextEdit"):
            return
        self._notes_before_edit = u.versionNotesTextEdit.toPlainText()
        u.versionNotesTextEdit.setReadOnly(False)
        u.versionNotesTextEdit.setFocus()
        self._set_notes_links(editing=True)

    def _on_asset_notes_save(self):
        """The "Save" link: write the notes to the repo's
        asset_notes.txt and lock the box again."""
        self._save_asset_notes()
        u = self.ui
        if hasattr(u, "versionNotesTextEdit"):
            u.versionNotesTextEdit.setReadOnly(True)
        self._set_notes_links(editing=False)

    def _on_asset_notes_cancel(self):
        """The "Cancel" link: discard the edits, restore the text
        the box had when Edit was pressed, lock it again. Nothing
        is written."""
        u = self.ui
        if hasattr(u, "versionNotesTextEdit"):
            u.versionNotesTextEdit.setPlainText(self._notes_before_edit)
            u.versionNotesTextEdit.setReadOnly(True)
        self._notes_dirty = False
        self._set_notes_links(editing=False)

    # -- Animation Notes ---------------------------------------------
    def _load_anim_notes(self, code, clip):
        """Notes text for a clip.

        The repo's assets/characters/<Folder>/animation_notes/
        <Clip>.txt wins when it exists; otherwise the clip's
        "note" field in characters.json (HitReactions has one);
        "" when neither exists.
        """
        from .core.config import anim_notes_path_for, clip_for
        path = anim_notes_path_for(self.config, code, clip)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return f.read()
        entry = clip_for(self.config, code, clip)
        if entry and entry.get("note"):
            return entry["note"]
        return ""

    def _save_anim_notes(self):
        """Save the Animation Notes box for the current clip.

        Same pattern as Asset Notes: only when the user actually
        typed (dirty flag), to assets/characters/<Folder>/
        animation_notes/<Clip>.txt in the tool repo. Called by the
        Save link, when switching clip or character, and when the
        window closes.
        """
        code = self.current_character
        clip = self.current_clip
        if not code or not clip or self.config is None:
            return
        if not hasattr(self.ui, "animationNotesTextEdit"):
            return
        if not self._anim_notes_dirty:
            return
        from .core.config import anim_notes_path_for
        notes_path = anim_notes_path_for(self.config, code, clip)
        text = self.ui.animationNotesTextEdit.toPlainText()
        try:
            existing = ""
            if os.path.exists(notes_path):
                with open(notes_path, encoding="utf-8") as f:
                    existing = f.read()
            if text != existing and (text or os.path.exists(notes_path)):
                os.makedirs(os.path.dirname(notes_path), exist_ok=True)
                with open(notes_path, "w", encoding="utf-8") as f:
                    f.write(text)
            self._anim_notes_dirty = False
        except OSError as e:
            self._set_status(f"Could not save animation notes for {clip}: {e}")

    def _on_anim_notes_changed(self):
        """The Animation Notes box changed. Only the user typing
        counts — loading notes (setPlainText while read-only) must
        not mark the notes dirty, or switching clip would write a
        file the user never touched."""
        if hasattr(self.ui, "animationNotesTextEdit") and \
                not self.ui.animationNotesTextEdit.isReadOnly():
            self._anim_notes_dirty = True

    def _set_anim_notes_links(self, editing):
        """Which Animation Notes links show: Edit alone in view
        mode, Save + Cancel in edit mode."""
        u = self.ui
        if hasattr(u, "animNotesEditLink"):
            u.animNotesEditLink.setVisible(not editing)
        if hasattr(u, "animNotesSaveLink"):
            u.animNotesSaveLink.setVisible(editing)
        if hasattr(u, "animNotesCancelLink"):
            u.animNotesCancelLink.setVisible(editing)

    def _on_anim_notes_edit(self):
        """The "Edit" link: unlock the box for typing, show Save +
        Cancel. The pre-edit text is remembered so Cancel can put
        it back."""
        u = self.ui
        if not hasattr(u, "animationNotesTextEdit"):
            return
        self._anim_notes_before_edit = u.animationNotesTextEdit.toPlainText()
        u.animationNotesTextEdit.setReadOnly(False)
        u.animationNotesTextEdit.setFocus()
        self._set_anim_notes_links(editing=True)

    def _on_anim_notes_save(self):
        """The "Save" link: write the notes to the repo's
        animation_notes/<Clip>.txt and lock the box again."""
        self._save_anim_notes()
        u = self.ui
        if hasattr(u, "animationNotesTextEdit"):
            u.animationNotesTextEdit.setReadOnly(True)
        self._set_anim_notes_links(editing=False)

    def _on_anim_notes_cancel(self):
        """The "Cancel" link: discard the edits, restore the text
        the box had when Edit was pressed, lock it again. Nothing
        is written."""
        u = self.ui
        if hasattr(u, "animationNotesTextEdit"):
            u.animationNotesTextEdit.setPlainText(self._anim_notes_before_edit)
            u.animationNotesTextEdit.setReadOnly(True)
        self._anim_notes_dirty = False
        self._set_anim_notes_links(editing=False)

    def closeEvent(self, event):
        self._save_asset_notes()
        self._save_anim_notes()
        self._save_geometry()
        super().closeEvent(event)

    # -- Mesh / Rig / Skin import rows --------------------------------
    _IMPORT_FILTERS = {
        "mesh": ("Mesh files (*.fbx *.obj *.ma *.mb)", "Mesh"),
        "rig": ("Maya files (*.ma *.mb)", "Rig"),
        "skin": ("Skin weights (*.json)", "Skin"),
    }

    def _row_path(self, kind, code=None):
        """Effective path for an import row: a Browse pick wins,
        otherwise the resolved default (None when nothing found)."""
        code = code or self.current_character
        if not code or self.config is None:
            return None
        override = self._import_paths.get(code, {}).get(kind)
        if override:
            return override
        if kind == "rig":
            from .core.config import rig_path_for
            return rig_path_for(self.config, code)
        if kind == "skin":
            from .core.config import skin_path_for
            path = skin_path_for(self.config, code)
            return path if os.path.exists(path) else None
        # mesh: newest .fbx, else newest .obj, model_dir then anim_dir
        from .core.config import get_character, resolve
        from .core.assets import latest_mesh_file
        ch = get_character(self.config, code)
        folders = [resolve(self.config, ch.get("model_dir", "")),
                   resolve(self.config, ch.get("anim_dir", ""))]
        return latest_mesh_file(folders)

    def _set_row(self, kind, path):
        names = {
            "mesh": ("meshPathLineEdit", "No mesh file — Browse to pick one"),
            "rig": ("rigImportPathLineEdit", ""),
            "skin": ("skinPathLineEdit", "No skin.json yet — Browse to pick one"),
        }
        name, empty_text = names[kind]
        line = getattr(self.ui, name, None)
        if line is None:
            return
        line.setText(path or "")
        line.setPlaceholderText("" if path else empty_text)

    def _last_modified_text(self, code):
        """One date for File info: the mesh file's mtime if found,
        else the rig file's, else "—"."""
        for path in (self._row_path("mesh", code), self._row_path("rig", code)):
            if path and os.path.exists(path):
                return time.strftime("%m/%d/%Y %H:%M",
                                     time.localtime(os.path.getmtime(path)))
        return "—"

    def _on_browse_import(self, kind):
        if not self.current_character:
            self._set_status("Select a character first.")
            return
        label, title = self._IMPORT_FILTERS[kind]
        start = ""
        current = self._row_path(kind)
        if current:
            start = os.path.dirname(current)
        elif self.config:
            start = self.config.get("project_root", "")
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, f"Pick the {kind} file", start, label)
        if path:
            self._import_paths.setdefault(
                self.current_character, {})[kind] = path
            self._set_row(kind, path)
            self._set_status(
                f"{title} file set to {path} for {self.current_character}.")

    def _on_import_mesh(self):
        path = self._row_path("mesh")
        if not path:
            self._set_status("Pick a mesh file first — Browse… next to Mesh.")
            return
        try:
            from .core.maya_bridge import import_file
            import_file(path)
            self._set_status(f"Imported mesh: {os.path.basename(path)}")
        except Exception as e:
            self._set_status(f"Import mesh needs Maya: {e}")

    def _on_import_rig(self):
        # Rig is always referenced, never imported — same flow as
        # the Reference button, using the path in the Rig row.
        self._on_reference_rig()

    def _on_import_skin(self):
        """Skin row: apply an ngSkinTools skin.json onto the
        referenced rig. The file is validated first (pure Python),
        then the weights go onto the namespaced skinned mesh."""
        code = self.current_character
        if not code:
            self._set_status("Select a character first.")
            return
        path = self._row_path("skin")
        if not path:
            self._set_status("Pick a skin.json first — Browse… next to Skin.")
            return
        try:
            from .core.maya_bridge import import_skin_weights
            from .core.config import namespace_for
            mesh, summary = import_skin_weights(
                path, namespace_for(self.config, code))
            self._set_status(
                f"Imported skin weights onto {mesh}: {summary}.")
        except Exception as e:
            self._set_status(f"Import skin: {e}")

    def _model_action(self, action):
        self._set_status(f"Model {action}: {self.current_character or '(no character)'} — wired to core.maya_bridge in the next pass.")
        # Next pass: open_file / reference_rig / import_file with namespace

    def _checked_validation_ids(self):
        """The check IDs ticked in the Validation checklist, or None
        when the checklist doesn't exist (the .ui fallback). An
        empty list means nothing is ticked — the caller reports
        "No checks selected" instead of running nothing."""
        u = self.ui
        if not hasattr(u, "validationChecksList"):
            return None
        check_ids = []
        for i in range(u.validationChecksList.count()):
            item = u.validationChecksList.item(i)
            if item.checkState() == QtCore.Qt.Checked:
                check_ids.append(item.data(QtCore.Qt.UserRole))
        return check_ids

    def _on_validate(self):
        """Run the CHECKED validation checks on the selected meshes.

        The checklist is validation/*.py, one row per file; only
        the ticked ones run. Untick a check to skip it for this run.
        """
        u = self.ui
        check_ids = self._checked_validation_ids()
        if check_ids is not None and not check_ids:
            u.validationResultsText.setPlainText(
                "No checks selected — tick at least one.")
            return
        try:
            from .core.validator import validate_selection, format_report
            results = validate_selection(check_ids)
            text = "\n\n".join(
                f"{mesh}:\n{format_report(r)}" for mesh, r in results.items())
            u.validationResultsText.setPlainText(text or "No meshes selected.")
        except Exception as e:
            u.validationResultsText.setPlainText(f"Validation needs Maya: {e}")

    def _on_repair(self):
        """Repair the failing CHECKED checks, then re-run them.

        Only three checks have an automatic fix: frozen transforms
        (freeze), construction history (delete history), origin
        (move the mesh to the origin). Manifold / n-gons / zero-area
        / textures need a human — the log says so per check, and
        the export gate is re-checked after the repairs.
        """
        u = self.ui
        check_ids = self._checked_validation_ids()
        if check_ids is not None and not check_ids:
            u.validationResultsText.setPlainText(
                "No checks selected — tick at least one.")
            return
        try:
            from .core.validator import repair_selection, format_repair_report
            outcomes = repair_selection(check_ids)
            text = "\n\n".join(
                f"{mesh}:\n{format_repair_report(o)}"
                for mesh, o in outcomes.items())
            u.validationResultsText.setPlainText(text or "No meshes selected.")
        except Exception as e:
            u.validationResultsText.setPlainText(f"Repair needs Maya: {e}")

    def _on_export_mesh(self):
        """Export Mesh: the character's mesh as FBX, materials embedded.

        The mesh FBX carries the material definitions AND the
        texture files inside it (FBX "Embed Media"), so the Unity
        side renders correctly without the texture/ folder.
        """
        code = self.current_character
        if not code:
            self._set_status("Select a character first.")
            return
        try:
            from .core.unity_export import export_mesh_fbx
            out = export_mesh_fbx(self.config, code)
            self._set_status(f"Exported mesh to {out} (materials embedded).")
        except Exception as e:
            self._set_status(f"Export Mesh needs Maya: {e}")

    def _on_export_rig(self):
        """Export Rig: the referenced rig (skeleton + skinned mesh) as FBX.

        The Unity character file — the one the animation clips
        retarget onto. Export Mesh is the mesh alone; Export Rig
        is the rigged character, no animation baked.
        """
        code = self.current_character
        if not code:
            self._set_status("Select a character first.")
            return
        try:
            from .core.unity_export import export_rig_fbx
            out = export_rig_fbx(self.config, code)
            self._set_status(f"Exported rig to {out}.")
        except Exception as e:
            self._set_status(f"Export Rig needs Maya: {e}")

    def _on_export_skin(self):
        """Export Skin: the rig's skin weights to skin.json.

        Written to <Character>/skinweight/skin.json (ngSkinTools
        export) — the same file Import Skin reads back.
        """
        code = self.current_character
        if not code:
            self._set_status("Select a character first.")
            return
        try:
            from .core.config import namespace_for, skin_path_for
            from .core.maya_bridge import export_skin_weights
            path = skin_path_for(self.config, code)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            mesh, summary = export_skin_weights(
                path, namespace_for(self.config, code))
            self._set_status(
                f"Exported skin weights for {mesh} to {path}: {summary}.")
        except Exception as e:
            self._set_status(f"Export Skin needs Maya: {e}")

    def _on_snapshot(self):
        self._set_status("Snapshot: saves a versioned copy — same pattern as Simple Tools 'Create snapshot'.")

    def _on_reference_rig(self):
        code = self.current_character
        if not code:
            self._set_status("Select a character first.")
            return
        path = self._row_path("rig")
        try:
            from .core.maya_bridge import reference_rig
            from .core.config import namespace_for
            namespace = namespace_for(self.config, code)
            ref = reference_rig(path, namespace)
            self._set_status(
                f"Referenced rig: {os.path.basename(path)} under "
                f"namespace {namespace} ({ref}).")
        except Exception as e:
            self._set_status(f"Reference rig needs Maya: {e}")

    def _on_import_anim(self):
        self._set_status("Import clip onto the referenced rig — namespace comes from the character, not the file.")

    def _on_export_anim(self):
        self._set_status("Export clip (.ma) — versioned, per-character folder.")

    def _on_export_anim_fbx(self):
        self._set_status("Export FBX → Unity: animation, baked, frame range from the Animation tab.")

    def _on_batch_export(self):
        self._set_status("Batch export all clips for this character — one FBX per clip, same skeleton.")

    def _on_browse_root(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "PMF project root")
        if folder:
            self._apply_project_root(folder)

    def _apply_project_root(self, folder):
        """Point the tool at an asset folder and remember it.

        The folder is the one holding the four character folders
        (Deckard/, Jacques/, Ryo/, Delilah/) — downloaded from
        Drive and placed anywhere. It is saved per-machine in
        pmf_local.json (next to characters.json, gitignored), so the
        shared characters.json never carries one machine's path.
        Returns True when the folder was accepted.
        """
        folder = (folder or "").strip()
        if not folder or not os.path.isdir(folder):
            self._set_status(f"Project folder not found: {folder or '(empty)'} — nothing changed.")
            return False
        if self.config is None:
            self.config = {"project": "PMF", "characters": []}
        self.config["project_root"] = folder
        from .core.config import save_project_root
        save_project_root(folder, self.config_path)
        self.ui.projectRootLineEdit.setText(folder)
        self._populate_characters()
        self._set_status(f"Project folder set to {folder} — saved for this machine. "
                         "Rig, texture and thumbnail paths now resolve from it.")
        return True

    def _set_status(self, text):
        self.ui.statusLabel.setText(text)


_window = None


def show(config_path=None):
    """Show the PMF window in Maya. Reuses the existing window if open."""
    global _window
    if QtWidgets is None:
        raise RuntimeError("No Qt binding found — run this inside Maya.")
    from .core.config import load_config
    config = load_config(config_path) if config_path else None
    if config is None:
        try:
            config = load_config()
        except Exception:
            config = {"project": "PMF", "characters": []}
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    parent = _maya_main_window()
    if _window is None:
        _window = PMFWindow(config=config, parent=parent, config_path=config_path)
    _window.show()
    return _window


if __name__ == "__main__":
    # Standalone preview: layout only, Maya calls will report "needs Maya".
    app = QtWidgets.QApplication(sys.argv)
    try:
        from .core.config import load_config
        cfg = load_config()
    except Exception:
        cfg = {"project": "PMF", "characters": []}
    w = PMFWindow(config=cfg)
    w.show()
    # PySide6: app.exec(); PySide2: app.exec_()
    sys.exit(getattr(app, "exec", app.exec_)())
