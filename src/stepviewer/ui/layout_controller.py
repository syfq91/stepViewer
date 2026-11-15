"""Turns pointer gestures in the plan view into placement edits."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from ..config import SNAP_THRESHOLD
from ..core.commands import (
    DeleteItemsCommand,
    DuplicateItemsCommand,
    TransformItemCommand,
    TransformItemsCommand,
)
from ..core.snapping import snap_xy
from ..viewer.camera import PERSPECTIVE, PLAN


class LayoutController(QObject):
    """Handler for :class:`~stepviewer.viewer.interaction.PlanInteractor`."""

    preview_changed = Signal(str, object)
    status_message = Signal(str)

    def __init__(self, project, viewport, undo_stack, selection, parent=None) -> None:
        super().__init__(parent)
        self._project = project
        self._viewport = viewport
        self._undo = undo_stack
        self._selection = selection
        self.mode = PERSPECTIVE

        self._drag: dict | None = None
        self._rotate: dict | None = None
        self._pan: tuple[int, int] | None = None

    def set_project(self, project) -> None:
        """Point the controller at a project loaded from disk."""
        self._drag = None
        self._rotate = None
        self._pan = None
        self._project = project

    @property
    def project(self):
        return self._project

    # ------------------------------------------------------------------ pointer
    def press(self, x: int, y: int, button: str, shift: bool, ctrl: bool) -> None:
        if self.mode != PLAN:
            return
        if button == "left":
            self._begin_drag(x, y)
        elif button == "middle":
            self._pan = (x, y)
        elif button == "right":
            self._begin_rotate(x, y)

    def move(self, x: int, y: int, shift: bool, ctrl: bool) -> None:
        if self.mode != PLAN:
            return
        if self._pan is not None:
            self._do_pan(x, y)
        elif self._rotate is not None:
            self._do_rotate(x, ctrl)
        elif self._drag is not None:
            self._do_drag(x, y)

    def release(self, x: int, y: int, button: str, shift: bool, ctrl: bool) -> None:
        if self.mode != PLAN:
            return
        if button == "middle":
            self._pan = None
        elif button == "left":
            self._end_drag()
        elif button == "right":
            self._end_rotate()

    def wheel(self, direction: int, x: int, y: int, shift: bool, ctrl: bool) -> None:
        if self.mode != PLAN:
            return
        self._viewport.camera.zoom(0.85 if direction > 0 else 1.0 / 0.85)
        self._render()

    def click(self, x: int, y: int) -> None:
        """Left click without dragging (used by the 3D view)."""
        if self.mode == PLAN:
            return
        item_id = self._viewport.scene.pick(x, y)
        self._selection.set([item_id] if item_id else [])

    # ------------------------------------------------------------------ dragging
    def _begin_drag(self, x: int, y: int) -> None:
        item_id = self._viewport.scene.pick(x, y)
        if item_id is None:
            self._selection.clear()
            self._render()
            return

        self._selection.set([item_id])
        item = self._project.get(item_id)
        if item is None or item.locked:
            return

        world = self._viewport.camera.display_to_world(x, y)
        self._drag = {
            "item_id": item_id,
            "start_placement": item.placement,
            "last": item.placement,
            "grab": (
                world[0] - item.placement.position[0],
                world[1] - item.placement.position[1],
            ),
            "start_display": (x, y),
            "moved": False,
        }

    def _do_drag(self, x: int, y: int) -> None:
        drag = self._drag
        if drag is None:
            return
        item = self._project.get(drag["item_id"])
        if item is None:
            return

        world = self._viewport.camera.display_to_world(x, y)
        proposed = (world[0] - drag["grab"][0], world[1] - drag["grab"][1])
        footprints = [
            other.footprint
            for other in self._project.items
            if other.id != item.id and other.visible
        ]
        grid = self._project.grid
        result = snap_xy(
            proposed,
            item.footprint_offset,
            footprints,
            grid.size,
            SNAP_THRESHOLD,
            grid_enabled=grid.snap,
        )

        placement = drag["start_placement"].moved_to_xy(*result.xy)
        drag["last"] = placement
        if (x, y) != drag["start_display"]:
            drag["moved"] = True

        self._viewport.scene.apply_placement(item.id, placement)
        self._viewport.scene.guides.show(result.guides)
        self.preview_changed.emit(item.id, placement)
        self.status_message.emit(
            f"{item.name}: x {placement.position[0]:.0f}  "
            f"y {placement.position[1]:.0f} mm"
        )
        self._render()

    def _end_drag(self) -> None:
        drag = self._drag
        self._drag = None
        if drag is None:
            return
        self._viewport.scene.guides.clear()
        if drag["moved"] and drag["last"] != drag["start_placement"]:
            self._undo.push(
                TransformItemCommand(
                    self._project,
                    drag["item_id"],
                    drag["start_placement"],
                    drag["last"],
                )
            )
        self._render()

    # ----------------------------------------------------------------- rotating
    def _begin_rotate(self, x: int, y: int) -> None:
        item_id = self._viewport.scene.pick(x, y)
        if item_id is None and len(self._selection.ids) == 1:
            item_id = self._selection.primary
        if item_id is None:
            return

        item = self._project.get(item_id)
        if item is None or item.locked:
            return

        self._selection.set([item_id])
        self._rotate = {
            "item_id": item_id,
            "start_placement": item.placement,
            "last": item.placement,
            "start_display": (x, y),
        }

    def _do_rotate(self, x: int, ctrl: bool) -> None:
        rotate = self._rotate
        if rotate is None:
            return
        item = self._project.get(rotate["item_id"])
        if item is None:
            return

        degrees = (x - rotate["start_display"][0]) * 0.5
        if ctrl:
            degrees = round(degrees / 15.0) * 15.0
        placement = rotate["start_placement"].rotated_by(degrees)
        rotate["last"] = placement

        self._viewport.scene.apply_placement(item.id, placement)
        self.preview_changed.emit(item.id, placement)
        self.status_message.emit(f"{item.name}: {placement.rotation_z:.0f} deg")
        self._render()

    def _end_rotate(self) -> None:
        rotate = self._rotate
        self._rotate = None
        if rotate is None:
            return
        if rotate["last"] != rotate["start_placement"]:
            self._undo.push(
                TransformItemCommand(
                    self._project,
                    rotate["item_id"],
                    rotate["start_placement"],
                    rotate["last"],
                )
            )
        self._render()

    def _do_pan(self, x: int, y: int) -> None:
        start = self._pan
        if start is None:
            return
        self._viewport.camera.pan(x - start[0], y - start[1])
        self._pan = (x, y)
        self._render()

    # ----------------------------------------------------------------- keyboard
    def rotate_selection(self, degrees: float) -> None:
        self._transform_selection(
            lambda placement: placement.rotated_by(degrees), "Rotate items"
        )

    def nudge_selection(self, dx: float, dy: float) -> None:
        def move(placement):
            x, y = placement.xy
            return placement.moved_to_xy(x + dx, y + dy)

        self._transform_selection(move, "Nudge items")

    def _transform_selection(self, change, label: str) -> None:
        changes = []
        for item_id in self._selection.ids:
            item = self._project.get(item_id)
            if item is None or item.locked:
                continue
            changes.append((item_id, item.placement, change(item.placement)))
        if changes:
            self._undo.push(TransformItemsCommand(self._project, changes, label))
            self._render()

    def delete_selection(self) -> None:
        ids = self._selection.ids
        if not ids:
            return
        self._undo.push(DeleteItemsCommand(self._project, ids))
        self._selection.clear()
        self._render()

    def duplicate_selection(self) -> None:
        ids = self._selection.ids
        if not ids:
            return
        command = DuplicateItemsCommand(self._project, ids)
        self._undo.push(command)
        copies = command.copy_ids
        if copies:
            self._selection.set(copies)
        self._render()

    def select_all(self) -> None:
        self._selection.set([item.id for item in self._project.items])

    def fit_view(self) -> None:
        self._viewport.camera.fit(self._project.items_bounds())
        self._render()

    # ----------------------------------------------------------------- internals
    def _render(self) -> None:
        self._viewport.render()
