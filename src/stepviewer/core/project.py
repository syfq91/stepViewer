"""The layout document: items, grid settings and JSON persistence."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import numpy as np

from ..cad.mesh import MeshData
from ..config import (
    AUTO_PLACE_GAP,
    DEFAULT_GRID_SIZE,
    PROJECT_FORMAT,
    PROJECT_VERSION,
    UNITS,
)
from .item import SceneItem
from .transform import Placement


class MissingSourceError(FileNotFoundError):
    """Raised when a project references a STEP file that cannot be used."""


class ProjectFormatError(ValueError):
    """Raised when a project file is not a StepViewer layout."""


@dataclass
class GridSettings:
    size: float = DEFAULT_GRID_SIZE
    snap: bool = True
    visible: bool = True


class Project:
    """Ordered collection of placed items plus the grid configuration."""

    def __init__(self) -> None:
        self.items: list[SceneItem] = []
        self.grid = GridSettings()
        self.path: Path | None = None
        self._listeners: list[Callable[[], None]] = []

    # ------------------------------------------------------------------ events
    def add_listener(self, listener: Callable[[], None]) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    # ----------------------------------------------------------------- lookups
    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self) -> Iterable[SceneItem]:
        return iter(self.items)

    def get(self, item_id: str) -> SceneItem | None:
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def index_of(self, item_id: str) -> int:
        for index, item in enumerate(self.items):
            if item.id == item_id:
                return index
        raise KeyError(item_id)

    def unique_name(self, base: str) -> str:
        taken = {item.name for item in self.items}
        if base not in taken:
            return base
        counter = 2
        while f"{base} {counter}" in taken:
            counter += 1
        return f"{base} {counter}"

    def items_bounds(self) -> tuple[np.ndarray, np.ndarray] | None:
        """Union of every visible item's world bounds."""
        lows, highs = [], []
        for item in self.items:
            if not item.visible:
                continue
            low, high = item.bounds
            lows.append(low)
            highs.append(high)
        if not lows:
            return None
        return np.min(lows, axis=0), np.max(highs, axis=0)

    # --------------------------------------------------------------- mutations
    def new_item(
        self,
        source_path: str,
        mesh: MeshData,
        source_sha1: str = "",
        placement: Placement | None = None,
        name: str | None = None,
        color: str | None = None,
    ) -> SceneItem:
        """Build (but do not insert) an item for a freshly imported model."""
        if placement is None:
            x, y = self.next_free_xy()
            placement = Placement((x, y, 0.0))
        return SceneItem(
            id=uuid.uuid4().hex,
            name=self.unique_name(name or Path(source_path).stem or "model"),
            source_path=str(source_path),
            mesh=mesh,
            placement=placement,
            color=color,
            source_sha1=source_sha1,
        )

    def make_duplicate(self, item: SceneItem, offset=(100.0, 100.0, 0.0)) -> SceneItem:
        x, y, z = item.placement.position
        return SceneItem(
            id=uuid.uuid4().hex,
            name=self.unique_name(Path(item.source_path).stem or item.name),
            source_path=item.source_path,
            mesh=item.mesh,
            placement=Placement(
                (x + offset[0], y + offset[1], z + offset[2]),
                item.placement.rotation_z,
                item.placement.scale,
            ),
            color=item.color,
            visible=item.visible,
            locked=item.locked,
            source_sha1=item.source_sha1,
        )

    def next_free_xy(self) -> tuple[float, float]:
        """Place new models to the right of whatever is already in the scene."""
        if not self.items:
            return 0.0, 0.0
        right = max(item.footprint[2] for item in self.items)
        step = self.grid.size if self.grid.size > 0 else DEFAULT_GRID_SIZE
        x = right + AUTO_PLACE_GAP
        return round(x / step) * step, 0.0

    def insert_item(self, item: SceneItem, index: int | None = None) -> None:
        if self.get(item.id) is not None:
            raise ValueError(f"item {item.id} is already in the project")
        if index is None or index > len(self.items):
            self.items.append(item)
        else:
            self.items.insert(max(0, index), item)
        self._notify()

    def remove_item(self, item_id: str) -> SceneItem | None:
        for index, item in enumerate(self.items):
            if item.id == item_id:
                del self.items[index]
                self._notify()
                return item
        return None

    def set_placement(self, item_id: str, placement: Placement) -> None:
        item = self.get(item_id)
        if item is None:
            return
        if placement.scale <= 0:
            raise ValueError("scale must be positive")
        item.placement = placement
        self._notify()

    def set_field(self, item_id: str, field: str, value) -> None:
        item = self.get(item_id)
        if item is None or not hasattr(item, field):
            return
        setattr(item, field, value)
        self._notify()

    # ------------------------------------------------------------ persistence
    def to_dict(self) -> dict:
        return {
            "format": PROJECT_FORMAT,
            "version": PROJECT_VERSION,
            "units": UNITS,
            "grid": {
                "size": float(self.grid.size),
                "snap": bool(self.grid.snap),
                "visible": bool(self.grid.visible),
            },
            "items": [item.to_dict() for item in self.items],
        }

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        if target.suffix != ".svproj":
            target = target.with_suffix(".svproj")
        target.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
        self.path = target
        self._notify()
        return target

    @classmethod
    def from_dict(
        cls,
        data: dict,
        mesh_provider: Callable[[str, str], MeshData],
    ) -> tuple["Project", list[tuple[str, str]]]:
        if data.get("format") != PROJECT_FORMAT:
            raise ProjectFormatError("not a StepViewer layout file")

        version = int(data.get("version", 0) or 0)
        if version > PROJECT_VERSION:
            raise ProjectFormatError(
                f"project version {version} is newer than this application supports"
            )

        project = cls()
        grid = data.get("grid") or {}
        project.grid = GridSettings(
            size=float(grid.get("size", DEFAULT_GRID_SIZE)),
            snap=bool(grid.get("snap", True)),
            visible=bool(grid.get("visible", True)),
        )

        problems: list[tuple[str, str]] = []
        for raw in data.get("items") or []:
            path = str(raw.get("source") or "")
            try:
                mesh = mesh_provider(path, str(raw.get("source_sha1") or ""))
                project.items.append(SceneItem.from_dict(raw, mesh))
            except Exception as exc:  # missing, unreadable or unsupported source
                problems.append((path, str(exc) or exc.__class__.__name__))
        return project, problems

    @classmethod
    def load(
        cls,
        path: str | Path,
        mesh_provider: Callable[[str, str], MeshData],
    ) -> tuple["Project", list[tuple[str, str]]]:
        source = Path(path)
        data = json.loads(source.read_text(encoding="utf-8"))
        project, problems = cls.from_dict(data, mesh_provider)
        project.path = source
        return project, problems
