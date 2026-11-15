"""Tree of everything placed in the layout."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

_LOCKED_COLOR = QColor("#7f858f")


class ScenePanel(QWidget):
    selection_changed = Signal(list)
    visibility_toggled = Signal(str, bool)
    rename_requested = Signal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Item", "Source"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setColumnWidth(0, 150)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.tree)

        self._updating = False
        self._order: list[str] = []
        self._names: dict[str, str] = {}
        self._visible: dict[str, bool] = {}
        self._selection: list[str] = []

    # ------------------------------------------------------------------ updates
    def sync(self, items) -> None:
        """Update the tree in place, rebuilding only when the item set changes."""
        items = list(items)
        ids = [item.id for item in items]
        if ids != self._order:
            self.set_items(items)
            return

        self._updating = True
        try:
            for index, item in enumerate(items):
                node = self.tree.topLevelItem(index)
                if node is None:
                    continue
                if node.text(0) != item.name:
                    node.setText(0, item.name)
                state = Qt.Checked if item.visible else Qt.Unchecked
                if node.checkState(0) != state:
                    node.setCheckState(0, state)
                node.setForeground(0, QBrush(_LOCKED_COLOR) if item.locked else QBrush())
                self._names[item.id] = item.name
                self._visible[item.id] = item.visible
        finally:
            self._updating = False
        self.set_selection(self._selection)

    def set_items(self, items) -> None:
        self._updating = True
        try:
            self.tree.clear()
            self._names.clear()
            self._visible.clear()
            self._order.clear()
            for item in items:
                node = QTreeWidgetItem([item.name, Path(item.source_path).name])
                node.setData(0, Qt.UserRole, item.id)
                node.setFlags(
                    node.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable
                )
                node.setCheckState(0, Qt.Checked if item.visible else Qt.Unchecked)
                node.setToolTip(0, item.source_path)
                node.setToolTip(1, item.source_path)
                if item.locked:
                    node.setForeground(0, QBrush(_LOCKED_COLOR))
                self._names[item.id] = item.name
                self._visible[item.id] = item.visible
                self._order.append(item.id)
                self.tree.addTopLevelItem(node)
        finally:
            self._updating = False
        self.set_selection(self._selection)

    def set_selection(self, item_ids) -> None:
        self._selection = list(item_ids)
        wanted = set(self._selection)
        self._updating = True
        try:
            for index in range(self.tree.topLevelItemCount()):
                node = self.tree.topLevelItem(index)
                node.setSelected(node.data(0, Qt.UserRole) in wanted)
        finally:
            self._updating = False

    # ------------------------------------------------------------------- events
    def _on_selection_changed(self) -> None:
        if self._updating:
            return
        ids = [
            node.data(0, Qt.UserRole)
            for node in self.tree.selectedItems()
            if node.data(0, Qt.UserRole)
        ]
        self.selection_changed.emit(ids)

    def _on_item_changed(self, node: QTreeWidgetItem, _column: int) -> None:
        if self._updating:
            return
        item_id = node.data(0, Qt.UserRole)
        if not item_id:
            return

        visible = node.checkState(0) == Qt.Checked
        if visible != self._visible.get(item_id):
            self._visible[item_id] = visible
            self.visibility_toggled.emit(item_id, visible)

        name = node.text(0).strip()
        if name and name != self._names.get(item_id):
            self._names[item_id] = name
            self.rename_requested.emit(item_id, name)
