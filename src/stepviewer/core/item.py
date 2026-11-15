"""A placed instance of an imported model."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..cad.mesh import MeshData
from ..config import DEFAULT_ITEM_COLOR
from .transform import (
    Placement,
    bounds_corners,
    bounds_of,
    footprint_of,
    transform_points,
)
from .transform import Footprint


@dataclass
class SceneItem:
    """One model placed in the layout.

    The mesh is shared with every other item imported from the same file; only
    the placement differs between copies.
    """

    id: str
    name: str
    source_path: str
    mesh: MeshData
    placement: Placement = field(default_factory=Placement)
    color: str | None = None
    visible: bool = True
    locked: bool = False
    source_sha1: str = ""

    @property
    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        """World-space ``(low, high)`` of the transformed mesh."""
        matrix = self.placement.matrix()
        corners = transform_points(matrix, bounds_corners(*self.mesh.bounds))
        return bounds_of(corners)

    @property
    def footprint(self) -> Footprint:
        """World-space ``(min_x, min_y, max_x, max_y)`` of the transformed mesh."""
        return footprint_of(self.mesh.bounds[0], self.mesh.bounds[1], self.placement)

    @property
    def footprint_offset(self) -> Footprint:
        """Footprint relative to the item position, used while dragging."""
        return footprint_of(
            self.mesh.bounds[0], self.mesh.bounds[1], self.placement, translate=False
        )

    @property
    def display_color(self) -> str:
        return self.color or DEFAULT_ITEM_COLOR

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "source": self.source_path,
            "source_sha1": self.source_sha1,
            "position": [round(float(v), 6) for v in self.placement.position],
            "rotation_z": round(float(self.placement.rotation_z), 6),
            "scale": round(float(self.placement.scale), 6),
            "color": self.color,
            "visible": bool(self.visible),
            "locked": bool(self.locked),
        }

    @classmethod
    def from_dict(cls, data: dict, mesh: MeshData) -> "SceneItem":
        position = data.get("position") or [0.0, 0.0, 0.0]
        if len(position) != 3:
            raise ValueError("position must have three components")
        placement = Placement(
            position=(float(position[0]), float(position[1]), float(position[2])),
            rotation_z=float(data.get("rotation_z", 0.0)),
            scale=float(data.get("scale", 1.0)),
        )
        if placement.scale <= 0:
            raise ValueError("scale must be positive")
        return cls(
            id=str(data["id"]),
            name=str(data.get("name") or "item"),
            source_path=str(data["source"]),
            mesh=mesh,
            placement=placement,
            color=data.get("color"),
            visible=bool(data.get("visible", True)),
            locked=bool(data.get("locked", False)),
            source_sha1=str(data.get("source_sha1") or ""),
        )
