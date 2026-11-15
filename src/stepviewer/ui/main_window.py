"""The application window: docks, menus, toolbar and all the wiring."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QUndoStack
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QToolBar,
)

from ..cad.exporter import StepExportError, export_step as write_step_file
from ..cad.loader import STEP_SUFFIXES, load_mesh_with_sha1
from ..config import (
    APP_NAME,
    DEFAULT_GRID_EXTENT,
    MAX_GRID_SIZE,
    MIN_GRID_SIZE,
)
from ..core.commands import (
    AddItemCommand,
    SetFieldCommand,
    TransformItemCommand,
)
from ..core.project import MissingSourceError, Project
from ..viewer.camera import PERSPECTIVE, PLAN
from .assets_panel import AssetsPanel
from .import_worker import ImportSignals, ImportTask
from .layout_controller import LayoutController
from .properties_panel import PropertiesPanel
from .scene_panel import ScenePanel
from .selection import Selection
from .viewport import Viewport

_STEP_FILTER = "STEP files (*.step *.stp *.STEP *.STP);;All files (*)"
_PROJECT_FILTER = "StepViewer layout (*.svproj);;All files (*)"


class MainWindow(QMainWindow):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.resize(1440, 900)

        self.project = Project()
        self._meshes: dict[str, object] = {}
        self._sha1: dict[str, str] = {}
        self._last_dir = str(Path.home())
        self._pending_imports = 0
        self._import_failures: list[tuple[str, str]] = []
        self._syncing = False
        self._closing = False

        self.undo = QUndoStack(self)
        self.selection = Selection(self)

        self.viewport = Viewport(self)
        self.setCentralWidget(self.viewport)

        self.controller = LayoutController(
            self.project, self.viewport, self.undo, self.selection, self
        )
        self.viewport.set_handler(self.controller)

        self._create_panels()
        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._create_statusbar()

        self.project.add_listener(self._sync_project)
        self.selection.changed.connect(self._on_selection_changed)
        self.controller.preview_changed.connect(self._on_preview)
        self.controller.status_message.connect(self._on_status_message)
        self.undo.canUndoChanged.connect(self.act_undo.setEnabled)
        self.undo.canRedoChanged.connect(self.act_redo.setEnabled)
        self.undo.cleanChanged.connect(lambda _clean: self._update_title())

        self._import_signals = ImportSignals(self)
        self._import_signals.loaded.connect(self._on_import_loaded)
        self._import_signals.failed.connect(self._on_import_failed)
        self._import_signals.finished.connect(self._on_import_finished)

        # OCCT is happy to mesh in parallel internally; do not run two files at
        # the same time on top of that.
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)

        self._set_mode(PLAN)
        self._update_actions()
        self._update_status()
        self._update_title()

    # ------------------------------------------------------------------- build
    def _create_panels(self) -> None:
        self.assets = AssetsPanel(self)
        self.assets.import_requested.connect(self.import_step_files)
        self.assets.place_requested.connect(self.place_source)

        self.scene_panel = ScenePanel(self)
        self.scene_panel.selection_changed.connect(self.selection.set)
        self.scene_panel.visibility_toggled.connect(self._on_visibility_toggled)
        self.scene_panel.rename_requested.connect(self._on_rename_requested)

        self.properties = PropertiesPanel(self)
        self.properties.placement_edited.connect(self._on_placement_edited)
        self.properties.field_edited.connect(self._on_field_edited)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.assets)
        splitter.addWidget(self.scene_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        left = QDockWidget("Library", self)
        left.setObjectName("library-dock")
        left.setWidget(splitter)
        left.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.LeftDockWidgetArea, left)

        right = QDockWidget("Properties", self)
        right.setObjectName("properties-dock")
        right.setWidget(self.properties)
        right.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        right.setMinimumWidth(280)
        self.addDockWidget(Qt.RightDockWidgetArea, right)

    def _action(
        self,
        text: str,
        slot,
        shortcut: str | None = None,
        *,
        checkable: bool = False,
        tip: str | None = None,
    ) -> QAction:
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.setCheckable(checkable)
        action.setToolTip(tip or text)
        action.setStatusTip(tip or text)
        # Slots read the action's own state when they need it, so the same
        # signature works whether or not the action is checkable.
        action.triggered.connect(lambda _checked=False: slot())
        return action

    def _create_actions(self) -> None:
        self.act_import = self._action(
            "&Import STEP…", self.import_step_files, "Ctrl+I", tip="Import STEP models"
        )
        self.act_open = self._action(
            "&Open layout…", self.open_project, "Ctrl+O", tip="Open a .svproj layout"
        )
        self.act_save = self._action("&Save", self.save_project, "Ctrl+S")
        self.act_save_as = self._action("Save &as…", self.save_project_as, "Ctrl+Shift+S")
        self.act_export_step = self._action(
            "&Export STEP…", self.export_step, "Ctrl+E", tip="Write the layout as one STEP file"
        )
        self.act_export_png = self._action(
            "Export &image…", self.export_png, "Ctrl+Shift+E"
        )
        self.act_quit = self._action("&Quit", self.close, "Ctrl+Q")

        self.act_undo = QAction("&Undo", self)
        self.act_undo.setShortcut(QKeySequence("Ctrl+Z"))
        self.act_undo.triggered.connect(self.undo.undo)
        self.act_undo.setEnabled(False)

        self.act_redo = QAction("&Redo", self)
        self.act_redo.setShortcut(QKeySequence("Ctrl+Shift+Z"))
        self.act_redo.triggered.connect(self.undo.redo)
        self.act_redo.setEnabled(False)

        self.act_duplicate = self._action("&Duplicate", self.controller.duplicate_selection, "Ctrl+D")
        self.act_delete = self._action("De&lete", self.controller.delete_selection, "Delete")
        self.act_select_all = self._action("Select &all", self.controller.select_all, "Ctrl+A")
        self.act_rotate_cw = self._action(
            "Rotate 90° clockwise", lambda: self.controller.rotate_selection(-90.0), "R"
        )
        self.act_rotate_ccw = self._action(
            "Rotate 90° anticlockwise", lambda: self.controller.rotate_selection(90.0), "Shift+R"
        )

        self.act_plan = self._action(
            "Plan view", lambda: self._set_mode(PLAN), "1", checkable=True
        )
        self.act_plan.setChecked(True)
        self.act_3d = self._action(
            "3D view", lambda: self._set_mode(PERSPECTIVE), "2", checkable=True
        )
        mode_group = QActionGroup(self)
        mode_group.addAction(self.act_plan)
        mode_group.addAction(self.act_3d)

        self.act_toggle_view = self._action(
            "Toggle plan / 3D",
            lambda: self._set_mode(PERSPECTIVE if self.viewport.mode == PLAN else PLAN),
            "Tab",
        )
        self.act_fit = self._action("Fit to layout", self.controller.fit_view, "F")
        self.act_snap = self._action(
            "Snap to grid", self._on_snap_toggled, "G", checkable=True
        )
        self.act_snap.setChecked(self.project.grid.snap)
        self.act_grid = self._action(
            "Show grid", self._on_grid_visibility_toggled, "Shift+G", checkable=True
        )
        self.act_grid.setChecked(self.project.grid.visible)
        self.act_shortcuts = self._action("Keyboard shortcuts", self.show_shortcuts, "F1")

        self._nudge_actions = []
        for label, dx, dy, key in (
            ("left", -1, 0, "Left"),
            ("right", 1, 0, "Right"),
            ("closer", 0, -1, "Down"),
            ("further", 0, 1, "Up"),
        ):
            for factor, prefix in ((1, ""), (10, "Shift+")):
                action = QAction(f"Nudge {label}", self)
                action.setShortcut(QKeySequence(prefix + key))
                action.triggered.connect(
                    lambda _checked=False, dx=dx, dy=dy, factor=factor: self.controller.nudge_selection(
                        dx * factor * self.project.grid.size,
                        dy * factor * self.project.grid.size,
                    )
                )
                self.addAction(action)
                self._nudge_actions.append(action)

    def _create_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addActions(
            [self.act_import, self.act_open, self.act_save, self.act_save_as]
        )
        file_menu.addSeparator()
        file_menu.addActions([self.act_export_step, self.act_export_png])
        file_menu.addSeparator()
        file_menu.addAction(self.act_quit)

        edit_menu = self.menuBar().addMenu("&Edit")
        edit_menu.addActions([self.act_undo, self.act_redo])
        edit_menu.addSeparator()
        edit_menu.addActions(
            [
                self.act_duplicate,
                self.act_delete,
                self.act_select_all,
                self.act_rotate_cw,
                self.act_rotate_ccw,
            ]
        )

        view_menu = self.menuBar().addMenu("&View")
        view_menu.addActions([self.act_plan, self.act_3d, self.act_toggle_view])
        view_menu.addSeparator()
        view_menu.addActions([self.act_fit, self.act_snap, self.act_grid])

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(self.act_shortcuts)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Main", self)
        toolbar.setObjectName("main-toolbar")
        toolbar.setMovable(False)
        toolbar.addAction(self.act_import)
        toolbar.addSeparator()
        toolbar.addActions([self.act_undo, self.act_redo])
        toolbar.addSeparator()
        toolbar.addActions([self.act_plan, self.act_3d, self.act_fit])
        toolbar.addSeparator()
        toolbar.addAction(self.act_snap)
        toolbar.addAction(self.act_grid)

        toolbar.addWidget(QLabel("  Grid "))
        self.grid_size = QDoubleSpinBox()
        self.grid_size.setRange(MIN_GRID_SIZE, MAX_GRID_SIZE)
        self.grid_size.setDecimals(0)
        self.grid_size.setSingleStep(50.0)
        self.grid_size.setSuffix(" mm")
        self.grid_size.setValue(self.project.grid.size)
        self.grid_size.setKeyboardTracking(False)
        self.grid_size.valueChanged.connect(self._on_grid_size_changed)
        toolbar.addWidget(self.grid_size)

        self.addToolBar(toolbar)

    def _create_statusbar(self) -> None:
        self.status_items = QLabel()
        self.status_grid = QLabel()
        self.status_units = QLabel("Units: mm")
        for label in (self.status_units, self.status_grid, self.status_items):
            self.statusBar().addPermanentWidget(label)

    # ------------------------------------------------------------------ project
    def _sync_project(self) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            items = list(self.project.items)
            existing = set(self.viewport.scene.item_ids())
            wanted = {item.id for item in items}

            for item_id in existing - wanted:
                self.viewport.scene.remove_item(item_id)
            for item in items:
                self.viewport.scene.update_item(item)

            self.scene_panel.sync(items)
            self.selection.keep_existing(wanted)
            self._refresh_properties()
            self._update_grid()
            self._update_status()
            self._update_actions()
        finally:
            self._syncing = False
        self.viewport.render()

    def _refresh_properties(self) -> None:
        """Keep the numeric fields in step with edits made elsewhere."""
        item = self.properties.item
        if item is None or self.project.get(item.id) is None:
            return
        self.properties.show_placement(item.placement)

    def _replace_project(self, project: Project) -> None:
        self.undo.clear()
        self.selection.clear()
        self.viewport.scene.replace_all([])
        self.project.remove_listener(self._sync_project)
        self.controller.set_project(project)
        self.project = project
        self.project.add_listener(self._sync_project)
        self.grid_size.setValue(project.grid.size)
        self.act_snap.setChecked(project.grid.snap)
        self.act_grid.setChecked(project.grid.visible)
        self._sync_project()
        self.controller.fit_view()
        self.undo.setClean()
        self._update_title()

    def _on_selection_changed(self, item_ids) -> None:
        self.viewport.scene.set_selection(item_ids)
        self.scene_panel.set_selection(item_ids)
        item = self.project.get(item_ids[0]) if len(item_ids) == 1 else None
        self.properties.set_item(item)
        self._update_actions()
        self.viewport.render()

    def _on_preview(self, item_id: str, placement) -> None:
        item = self.project.get(item_id)
        if item is not None and self.selection.ids == [item_id]:
            self.properties.show_placement(placement)

    def _on_status_message(self, message: str) -> None:
        self.statusBar().showMessage(message, 4000)

    # ---------------------------------------------------------------- selection
    def _on_visibility_toggled(self, item_id: str, visible: bool) -> None:
        item = self.project.get(item_id)
        if item is None or item.visible == visible:
            return
        self.undo.push(SetFieldCommand(self.project, item_id, "visible", item.visible, visible))

    def _on_rename_requested(self, item_id: str, name: str) -> None:
        item = self.project.get(item_id)
        if item is None or item.name == name:
            return
        self.undo.push(SetFieldCommand(self.project, item_id, "name", item.name, name, "Rename"))

    def _on_placement_edited(self, item_id: str, placement) -> None:
        item = self.project.get(item_id)
        if item is None or item.placement == placement:
            return
        self.undo.push(
            TransformItemCommand(self.project, item_id, item.placement, placement)
        )

    def _on_field_edited(self, item_id: str, field: str, value) -> None:
        item = self.project.get(item_id)
        if item is None:
            return
        before = getattr(item, field)
        if before == value:
            return
        label = {"color": "Change colour", "name": "Rename"}.get(field)
        self.undo.push(SetFieldCommand(self.project, item_id, field, before, value, label))

    # ------------------------------------------------------------------- import
    def import_step_files(self, paths=None) -> None:
        if not paths:
            paths, _ = QFileDialog.getOpenFileNames(
                self, "Import STEP files", self._last_dir, _STEP_FILTER
            )
        paths = [str(path) for path in paths or [] if str(path)]
        if not paths:
            return

        self._last_dir = str(Path(paths[0]).parent)
        start_batch = self._pending_imports == 0
        self._pending_imports += len(paths)
        self._import_failures.clear()
        self.statusBar().showMessage(
            f"Importing {len(paths)} file(s)…", 0
        )
        if start_batch:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        for path in paths:
            self._pool.start(ImportTask(path, self._import_signals))

    def _on_import_loaded(self, path: str, mesh, sha1: str) -> None:
        self._meshes[path] = mesh
        self._sha1[path] = sha1
        self.assets.add_source(path)

        item = self.project.new_item(path, mesh, sha1)
        self.undo.push(AddItemCommand(self.project, item))
        self.selection.set([item.id])
        self._on_status_message(
            f"{Path(path).name}: {mesh.triangle_count:,} triangles"
        )

    def _on_import_failed(self, path: str, message: str) -> None:
        self._import_failures.append((path, message))

    def _on_import_finished(self) -> None:
        self._pending_imports = max(0, self._pending_imports - 1)
        if self._pending_imports:
            return

        QApplication.restoreOverrideCursor()
        self.statusBar().clearMessage()

        if self._import_failures:
            details = "\n".join(
                f"{Path(path).name}: {message}" for path, message in self._import_failures
            )
            QMessageBox.warning(
                self, "Some files could not be imported", details
            )
            self._import_failures.clear()

        if self.project.items:
            self.controller.fit_view()
        self._update_status()

    def place_source(self, path: str) -> None:
        mesh = self._meshes.get(path)
        if mesh is None:
            self.import_step_files([path])
            return
        item = self.project.new_item(path, mesh, self._sha1.get(path, ""))
        self.undo.push(AddItemCommand(self.project, item))
        self.selection.set([item.id])

    # ------------------------------------------------------------------- files
    def _mesh_provider(self, path: str, sha1: str):
        if not path:
            raise MissingSourceError("the layout item has no source file")
        cached = self._meshes.get(path)
        if cached is not None:
            return cached
        if not Path(path).is_file():
            raise MissingSourceError(f"file not found: {path}")
        mesh, actual_sha1 = load_mesh_with_sha1(path)
        self._meshes[path] = mesh
        self._sha1[path] = actual_sha1
        self.assets.add_source(path)
        return mesh

    def open_project(self, path=None) -> None:
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self, "Open layout", self._last_dir, _PROJECT_FILTER
            )
        if not path:
            return

        self._last_dir = str(Path(path).parent)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            project, problems = Project.load(path, self._mesh_provider)
        except Exception as exc:
            QMessageBox.critical(self, "Could not open layout", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()

        self._replace_project(project)
        if problems:
            details = "\n".join(
                f"{Path(source).name}: {reason}" for source, reason in problems
            )
            QMessageBox.warning(
                self,
                "Some models could not be restored",
                "These items were skipped:\n\n" + details,
            )

    def save_project(self) -> None:
        if self.project.path is None:
            self.save_project_as()
            return
        self._save_to(self.project.path)

    def save_project_as(self) -> None:
        suggested = self.project.path or Path(self._last_dir) / "layout.svproj"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save layout", str(suggested), _PROJECT_FILTER
        )
        if path:
            self._save_to(path)

    def _save_to(self, path) -> None:
        try:
            written = self.project.save(path)
        except OSError as exc:
            QMessageBox.critical(self, "Could not save layout", str(exc))
            return
        self._last_dir = str(written.parent)
        self.undo.setClean()
        self._update_title()
        self.statusBar().showMessage(f"Saved {written.name}", 4000)

    def export_step(self) -> None:
        items = [item for item in self.project.items if item.visible]
        if not items:
            QMessageBox.information(
                self, "Nothing to export", "Import and place at least one model first."
            )
            return

        suggested = (
            self.project.path.with_suffix(".step")
            if self.project.path
            else Path(self._last_dir) / "layout.step"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Export STEP", str(suggested), "STEP (*.step)"
        )
        if not path:
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            written = write_step_file(items, path)
        except StepExportError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()

        self.statusBar().showMessage(
            f"Exported {len(items)} item(s) to {written.name}", 6000
        )

    def export_png(self) -> None:
        from vtkmodules.vtkIOImage import vtkPNGWriter
        from vtkmodules.vtkRenderingCore import vtkWindowToImageFilter

        suggested = str(Path(self._last_dir) / "layout.png")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export image", suggested, "PNG image (*.png)"
        )
        if not path:
            return

        self.viewport.render()
        capture = vtkWindowToImageFilter()
        capture.SetInput(self.viewport.render_window)
        capture.SetScale(2)
        capture.ReadFrontBufferOff()
        capture.Update()

        writer = vtkPNGWriter()
        writer.SetFileName(path)
        writer.SetInputConnection(capture.GetOutputPort())
        if not writer.Write():
            QMessageBox.critical(self, "Export failed", f"Could not write {path}")
            return
        self.statusBar().showMessage(f"Saved {Path(path).name}", 4000)

    def open_paths(self, paths) -> None:
        for path in paths:
            if str(path).lower().endswith(".svproj"):
                self.open_project(str(path))
            elif Path(path).suffix.lower() in STEP_SUFFIXES:
                self.import_step_files([str(path)])

    # -------------------------------------------------------------------- views
    def _set_mode(self, mode: str) -> None:
        self.viewport.set_mode(mode)
        self.act_plan.setChecked(mode == PLAN)
        self.act_3d.setChecked(mode == PERSPECTIVE)

    def _on_snap_toggled(self) -> None:
        self.project.grid.snap = self.act_snap.isChecked()
        self._update_status()

    def _on_grid_visibility_toggled(self) -> None:
        self.project.grid.visible = self.act_grid.isChecked()
        self._update_grid()
        self.viewport.render()

    def _on_grid_size_changed(self, value: float) -> None:
        self.project.grid.size = max(MIN_GRID_SIZE, float(value))
        self._update_grid()
        self._update_status()
        self.viewport.render()

    def _update_grid(self) -> None:
        extent = DEFAULT_GRID_EXTENT
        bounds = self.project.items_bounds()
        if bounds is not None:
            far = max(abs(float(value)) for value in (*bounds[0], *bounds[1]))
            extent = max(extent, far * 1.3)
        self.viewport.scene.update_grid(
            self.project.grid.size, extent, self.project.grid.visible
        )

    # --------------------------------------------------------------- status/title
    def _update_status(self) -> None:
        count = len(self.project.items)
        self.status_items.setText(f"{count} item" + ("s" if count != 1 else ""))
        grid = self.project.grid
        self.status_grid.setText(
            f"Snap {'on' if grid.snap else 'off'} · {grid.size:g} mm"
        )

    def _update_actions(self) -> None:
        has_selection = bool(self.selection.ids)
        for action in (
            self.act_delete,
            self.act_duplicate,
            self.act_rotate_cw,
            self.act_rotate_ccw,
        ):
            action.setEnabled(has_selection)
        self.act_select_all.setEnabled(bool(self.project.items))

    def _update_title(self) -> None:
        if self._closing:
            return
        try:
            clean = self.undo.isClean()
        except RuntimeError:
            # Qt can destroy the undo stack before the window while shutting down.
            return
        name = self.project.path.name if self.project.path else "Untitled layout"
        dirty = "" if clean else "*"
        self.setWindowTitle(f"{dirty}{name} — {APP_NAME}")

    def show_shortcuts(self) -> None:
        QMessageBox.information(
            self,
            "Keyboard shortcuts",
            "Plan view\n"
            "  Left drag          move item (snaps to grid and neighbours)\n"
            "  Right drag         rotate item\n"
            "  Middle drag        pan\n"
            "  Mouse wheel        zoom\n\n"
            "Everywhere\n"
            "  Tab                plan / 3D\n"
            "  1 / 2              plan / 3D\n"
            "  F                  fit to layout\n"
            "  G                  toggle grid snapping\n"
            "  Shift+G            toggle grid display\n"
            "  R / Shift+R        rotate 90°\n"
            "  Arrow keys         nudge by one grid step (Shift = 10 steps)\n"
            "  Ctrl+D             duplicate\n"
            "  Delete             delete selection\n"
            "  Ctrl+Z             undo\n"
            "  Ctrl+Shift+Z       redo\n"
            "  Ctrl+I             import STEP files\n"
            "  Ctrl+S             save layout\n"
            "  Ctrl+E             export STEP",
        )

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if not self.undo.isClean():
            choice = QMessageBox.question(
                self,
                "Unsaved layout",
                "Save your layout before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save,
            )
            if choice == QMessageBox.Cancel:
                event.ignore()
                return
            if choice == QMessageBox.Save:
                self.save_project()
                if not self.undo.isClean():
                    event.ignore()
                    return
        self._closing = True
        super().closeEvent(event)
