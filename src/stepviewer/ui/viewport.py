"""Qt wrapper around the VTK render window."""

from __future__ import annotations

import os

os.environ.setdefault("QT_API", "pyside6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from vtkmodules.vtkRenderingCore import vtkRenderer

from ..viewer.camera import PERSPECTIVE, PLAN, CameraController
from ..viewer.interaction import PlanInteractor, attach_click_picker, make_orbit_style
from ..viewer.scene import SceneView


class Viewport(QWidget):
    """The 3D canvas plus the interaction styles for both view modes."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.widget = QVTKRenderWindowInteractor(self)
        self.widget.setFocusPolicy(Qt.StrongFocus)
        layout.addWidget(self.widget)

        self.render_window = self.widget.GetRenderWindow()
        self.renderer = vtkRenderer()
        self.render_window.AddRenderer(self.renderer)
        self.interactor = self.render_window.GetInteractor()

        self.scene = SceneView(self.renderer)
        self.camera = CameraController(self.renderer)

        self.mode = PERSPECTIVE
        self._orbit_style = make_orbit_style()
        self._plan_style: PlanInteractor | None = None
        self._handler = None
        self._started = False

        self.interactor.SetInteractorStyle(self._orbit_style)
        self.widget.Initialize()

    # ------------------------------------------------------------------ wiring
    def set_handler(self, handler) -> None:
        """Attach the object that turns gestures into layout edits."""
        self._handler = handler
        self._plan_style = PlanInteractor(self.interactor, handler)
        attach_click_picker(self.interactor, handler.click)
        self.interactor.SetInteractorStyle(
            self._plan_style if self.mode == PLAN else self._orbit_style
        )

    def set_mode(self, mode: str) -> None:
        if mode not in (PLAN, PERSPECTIVE):
            raise ValueError(f"unknown view mode: {mode!r}")
        if mode == self.mode:
            return
        self.mode = mode
        if mode == PLAN and self._plan_style is not None:
            self.interactor.SetInteractorStyle(self._plan_style)
        else:
            self.interactor.SetInteractorStyle(self._orbit_style)
        self.camera.set_mode(mode)
        if self._handler is not None:
            self._handler.mode = mode
        self.render()

    def toggle_mode(self) -> str:
        self.set_mode(PERSPECTIVE if self.mode == PLAN else PLAN)
        return self.mode

    def render(self) -> None:
        if not self._started:
            return
        self.render_window.Render()

    # ------------------------------------------------------------------- events
    def showEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().showEvent(event)
        if not self._started:
            self._started = True
            self.widget.Start()
        self.render()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self.widget.Finalize()
        super().closeEvent(event)
