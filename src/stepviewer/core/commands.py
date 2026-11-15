"""Undo/redo commands built on ``QUndoStack``."""

from __future__ import annotations

from PySide6.QtGui import QUndoCommand

from .item import SceneItem
from .project import Project
from .transform import Placement


class AddItemCommand(QUndoCommand):
    def __init__(self, project: Project, item: SceneItem, index: int | None = None) -> None:
        super().__init__(f"Add {item.name}")
        self._project = project
        self._item = item
        self._index = index

    def redo(self) -> None:
        self._project.insert_item(self._item, self._index)
        self._index = self._project.index_of(self._item.id)

    def undo(self) -> None:
        self._project.remove_item(self._item.id)


class DeleteItemsCommand(QUndoCommand):
    def __init__(self, project: Project, item_ids: list[str]) -> None:
        count = len(item_ids)
        super().__init__(f"Delete {count} item" + ("s" if count != 1 else ""))
        self._project = project
        entries = []
        for item_id in item_ids:
            item = project.get(item_id)
            if item is not None:
                entries.append((project.index_of(item_id), item))
        self._entries = sorted(entries, key=lambda entry: entry[0])

    def redo(self) -> None:
        for _, item in reversed(self._entries):
            self._project.remove_item(item.id)

    def undo(self) -> None:
        for index, item in self._entries:
            self._project.insert_item(item, index)


class TransformItemCommand(QUndoCommand):
    def __init__(
        self,
        project: Project,
        item_id: str,
        before: Placement,
        after: Placement,
    ) -> None:
        item = project.get(item_id)
        label = item.name if item is not None else "item"
        super().__init__(f"Move {label}")
        self._project = project
        self._item_id = item_id
        self._before = before
        self._after = after

    def redo(self) -> None:
        self._project.set_placement(self._item_id, self._after)

    def undo(self) -> None:
        self._project.set_placement(self._item_id, self._before)


class TransformItemsCommand(QUndoCommand):
    """Move or rotate a group of items as one undo step."""

    def __init__(
        self,
        project: Project,
        changes: list[tuple[str, Placement, Placement]],
        label: str = "Move items",
    ) -> None:
        super().__init__(label)
        self._project = project
        self._changes = changes

    def redo(self) -> None:
        for item_id, _, after in self._changes:
            self._project.set_placement(item_id, after)

    def undo(self) -> None:
        for item_id, before, _ in self._changes:
            self._project.set_placement(item_id, before)


class SetFieldCommand(QUndoCommand):
    """Undoable change of a single item attribute (name, colour, flags)."""

    def __init__(
        self,
        project: Project,
        item_id: str,
        field: str,
        before,
        after,
        label: str | None = None,
    ) -> None:
        super().__init__(label or f"Change {field}")
        self._project = project
        self._item_id = item_id
        self._field = field
        self._before = before
        self._after = after

    def redo(self) -> None:
        self._project.set_field(self._item_id, self._field, self._after)

    def undo(self) -> None:
        self._project.set_field(self._item_id, self._field, self._before)


class DuplicateItemsCommand(QUndoCommand):
    def __init__(self, project: Project, item_ids: list[str]) -> None:
        copies: list[SceneItem] = []
        for item_id in item_ids:
            item = project.get(item_id)
            if item is not None:
                copies.append(project.make_duplicate(item))
        self._project = project
        self._copies = copies
        count = len(copies)
        super().__init__(f"Duplicate {count} item" + ("s" if count != 1 else ""))

    @property
    def copy_ids(self) -> list[str]:
        return [item.id for item in self._copies]

    def redo(self) -> None:
        for item in self._copies:
            self._project.insert_item(item)

    def undo(self) -> None:
        for item in reversed(self._copies):
            self._project.remove_item(item.id)
