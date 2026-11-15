"""Which items are currently selected."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class Selection(QObject):
    changed = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._ids: list[str] = []

    @property
    def ids(self) -> list[str]:
        return list(self._ids)

    @property
    def primary(self) -> str | None:
        """The item whose properties are shown (the last one selected)."""
        return self._ids[-1] if self._ids else None

    def set(self, item_ids) -> None:
        ids = [item_id for item_id in dict.fromkeys(item_ids)]
        if ids == self._ids:
            return
        self._ids = ids
        self.changed.emit(self.ids)

    def toggle(self, item_id: str) -> None:
        if item_id in self._ids:
            self._ids.remove(item_id)
        else:
            self._ids.append(item_id)
        self.changed.emit(self.ids)

    def clear(self) -> None:
        self.set([])

    def keep_existing(self, existing_ids) -> None:
        """Drop selections pointing at items that no longer exist."""
        existing = set(existing_ids)
        kept = [item_id for item_id in self._ids if item_id in existing]
        if kept != self._ids:
            self._ids = kept
            self.changed.emit(self.ids)
