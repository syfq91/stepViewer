"""List of STEP files that have been imported into this session."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class AssetsPanel(QWidget):
    import_requested = Signal()
    place_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setAlternatingRowColors(True)
        self.list.setToolTip("Double click a model to place another copy")
        self.list.itemDoubleClicked.connect(self._on_double_click)

        heading = QLabel("Imported models")
        heading.setStyleSheet("font-weight: 600;")

        button = QPushButton("Import STEP…")
        button.clicked.connect(self.import_requested)

        layout.addWidget(heading)
        layout.addWidget(self.list, 1)
        layout.addWidget(button)

    def add_source(self, path: str) -> None:
        for index in range(self.list.count()):
            if self.list.item(index).data(Qt.UserRole) == path:
                return
        entry = QListWidgetItem(Path(path).name)
        entry.setData(Qt.UserRole, path)
        entry.setToolTip(path)
        self.list.addItem(entry)

    def _on_double_click(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.UserRole)
        if path:
            self.place_requested.emit(str(path))
