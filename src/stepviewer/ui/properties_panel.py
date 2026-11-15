"""Numeric editing of the selected item's placement and display settings."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.transform import Placement


def _spin(minimum: float, maximum: float, suffix: str, decimals: int, step: float) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(minimum, maximum)
    box.setDecimals(decimals)
    box.setSingleStep(step)
    box.setSuffix(suffix)
    box.setKeyboardTracking(False)
    box.setAccelerated(True)
    return box


class PropertiesPanel(QWidget):
    placement_edited = Signal(str, object)
    field_edited = Signal(str, str, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._item = None
        self._updating = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)

        self.name = QLineEdit()
        self.name.editingFinished.connect(self._on_name_changed)

        identity = QGroupBox("Item")
        identity_layout = QFormLayout(identity)
        identity_layout.addRow("Name", self.name)

        self.x = _spin(-1e6, 1e6, " mm", 1, 50.0)
        self.y = _spin(-1e6, 1e6, " mm", 1, 50.0)
        self.z = _spin(-1e6, 1e6, " mm", 1, 50.0)
        self.rotation = _spin(-3600.0, 3600.0, " °", 1, 15.0)
        self.scale = _spin(0.001, 1000.0, " ×", 3, 0.1)

        transform = QGroupBox("Placement")
        transform_layout = QFormLayout(transform)
        transform_layout.addRow("X", self.x)
        transform_layout.addRow("Y", self.y)
        transform_layout.addRow("Z", self.z)
        transform_layout.addRow("Rotation", self.rotation)
        transform_layout.addRow("Scale", self.scale)

        for box in (self.x, self.y, self.z, self.rotation, self.scale):
            box.editingFinished.connect(self._on_placement_changed)

        self.color_button = QPushButton("Choose…")
        self.color_button.clicked.connect(self._on_pick_colour)
        self.color_reset = QPushButton("Reset")
        self.color_reset.clicked.connect(self._on_reset_colour)
        colour_row = QWidget()
        colour_layout = QHBoxLayout(colour_row)
        colour_layout.setContentsMargins(0, 0, 0, 0)
        colour_layout.addWidget(self.color_button, 1)
        colour_layout.addWidget(self.color_reset)

        self.visible = QCheckBox("Visible")
        self.locked = QCheckBox("Locked (cannot be dragged)")
        self.visible.toggled.connect(lambda checked: self._emit_field("visible", checked))
        self.locked.toggled.connect(lambda checked: self._emit_field("locked", checked))

        display = QGroupBox("Display")
        display_layout = QFormLayout(display)
        display_layout.addRow("Colour", colour_row)
        display_layout.addRow(self.visible)
        display_layout.addRow(self.locked)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("color: #8a8f98;")

        outer.addWidget(identity)
        outer.addWidget(transform)
        outer.addWidget(display)
        outer.addWidget(self.summary)
        outer.addStretch(1)

        self.set_item(None)

    # -------------------------------------------------------------------- state
    @property
    def item(self):
        return self._item

    def set_item(self, item) -> None:
        self._item = item
        enabled = item is not None
        for widget in (
            self.name,
            self.x,
            self.y,
            self.z,
            self.rotation,
            self.scale,
            self.color_button,
            self.color_reset,
            self.visible,
            self.locked,
        ):
            widget.setEnabled(enabled)

        self._updating = True
        try:
            if item is None:
                self.name.clear()
                for box in (self.x, self.y, self.z, self.rotation):
                    box.setValue(0.0)
                self.scale.setValue(1.0)
                self.visible.setChecked(False)
                self.locked.setChecked(False)
                self.color_button.setStyleSheet("")
                self.summary.setText("Nothing selected.")
            else:
                self.name.setText(item.name)
                self.show_placement(item.placement)
                self.visible.setChecked(item.visible)
                self.locked.setChecked(item.locked)
                self._show_colour(item.display_color)
                self.summary.setText(
                    f"{item.mesh.triangle_count:,} triangles\n{item.source_path}"
                )
        finally:
            self._updating = False

    def show_placement(self, placement: Placement) -> None:
        """Display a placement without emitting an edit (used while dragging)."""
        self._updating = True
        try:
            self.x.setValue(placement.position[0])
            self.y.setValue(placement.position[1])
            self.z.setValue(placement.position[2])
            self.rotation.setValue(placement.rotation_z)
            self.scale.setValue(placement.scale)
        finally:
            self._updating = False

    # ------------------------------------------------------------------- events
    def _current_placement(self) -> Placement:
        return Placement(
            position=(self.x.value(), self.y.value(), self.z.value()),
            rotation_z=self.rotation.value(),
            scale=max(self.scale.value(), 1e-6),
        )

    def _on_placement_changed(self) -> None:
        if self._updating or self._item is None:
            return
        placement = self._current_placement()
        if placement == self._item.placement:
            return
        self.placement_edited.emit(self._item.id, placement)

    def _on_name_changed(self) -> None:
        if self._updating or self._item is None:
            return
        name = self.name.text().strip()
        if name and name != self._item.name:
            self._emit_field("name", name)

    def _on_pick_colour(self) -> None:
        if self._item is None:
            return
        current = QColor(self._item.display_color)
        chosen = QColorDialog.getColor(current, self, "Item colour")
        if not chosen.isValid():
            return
        self._show_colour(chosen.name())
        self._emit_field("color", chosen.name())

    def _on_reset_colour(self) -> None:
        if self._item is None:
            return
        self._show_colour(None)
        self._emit_field("color", None)

    def _show_colour(self, color: str | None) -> None:
        if color:
            self.color_button.setStyleSheet(
                f"background-color: {color}; border: 1px solid #555; padding: 3px;"
            )
            self.color_button.setText(color)
        else:
            self.color_button.setStyleSheet("")
            self.color_button.setText("From model")

    def _emit_field(self, field: str, value) -> None:
        if self._updating or self._item is None:
            return
        self.field_edited.emit(self._item.id, field, value)
