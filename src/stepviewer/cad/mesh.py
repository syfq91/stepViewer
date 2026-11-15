"""Triangulated geometry in memory, independent of Qt and VTK."""

from __future__ import annotations

import numpy as np

from ..config import DEFAULT_ITEM_COLOR
from ..core.transform import bounds_of


def parse_color(value) -> np.ndarray:
    """Convert ``#rrggbb`` / ``#rrggbbaa`` / an RGBA tuple into a uint8 RGBA row."""
    if isinstance(value, str):
        text = value.strip().lstrip("#")
        if len(text) == 3:
            text = "".join(ch * 2 for ch in text)
        if len(text) not in (6, 8):
            raise ValueError(f"unsupported colour: {value!r}")
        channels = [int(text[i : i + 2], 16) for i in range(0, len(text), 2)]
        if len(channels) == 3:
            channels.append(255)
        return np.asarray(channels, dtype=np.uint8)
    channels = list(value)
    if len(channels) == 3:
        channels.append(255)
    if len(channels) != 4:
        raise ValueError(f"unsupported colour: {value!r}")
    return np.asarray([int(c) for c in channels], dtype=np.uint8)


class MeshData:
    """Vertices, triangles and per-vertex colours for one imported model.

    Instances are treated as immutable and shared between every item that uses
    the same source file.
    """

    __slots__ = ("vertices", "faces", "colors", "bounds")

    def __init__(
        self,
        vertices: np.ndarray,
        faces: np.ndarray,
        colors: np.ndarray,
        bounds: tuple[np.ndarray, np.ndarray],
    ) -> None:
        self.vertices = vertices
        self.faces = faces
        self.colors = colors
        self.bounds = bounds

    @classmethod
    def create(
        cls,
        vertices,
        faces,
        colors=None,
        default_color: str = DEFAULT_ITEM_COLOR,
    ) -> "MeshData":
        verts = np.array(vertices, dtype=np.float32).reshape(-1, 3)
        tris = np.array(faces, dtype=np.int32).reshape(-1, 3)

        finite = np.isfinite(verts).all(axis=1)
        if not finite.all():
            remap = np.full(len(verts), -1, dtype=np.int32)
            remap[finite] = np.arange(int(finite.sum()), dtype=np.int32)
            tris = tris[(remap[tris] >= 0).all(axis=1)]
            tris = remap[tris]
            verts = verts[finite]

        if len(verts) == 0 or len(tris) == 0:
            raise ValueError("mesh has no usable geometry")

        if colors is None:
            color_data = np.tile(parse_color(default_color), (len(verts), 1))
        else:
            color_data = np.array(colors, dtype=np.uint8).reshape(-1, 4)
            if len(color_data) == 1:
                color_data = np.tile(color_data, (len(verts), 1))
            elif len(color_data) != len(verts):
                raise ValueError("colour array does not match vertex count")

        verts = np.ascontiguousarray(verts)
        tris = np.ascontiguousarray(tris)
        color_data = np.ascontiguousarray(color_data)
        low, high = bounds_of(verts)
        return cls(verts, tris, color_data, (low, high))

    @classmethod
    def combined(cls, meshes) -> "MeshData":
        """Merge several meshes into a single one."""
        parts = [m for m in meshes if m is not None]
        if not parts:
            raise ValueError("nothing to combine")
        if len(parts) == 1:
            return parts[0]

        offsets = []
        running = 0
        for part in parts:
            offsets.append(running)
            running += len(part.vertices)

        vertices = np.concatenate([p.vertices for p in parts])
        faces = np.concatenate(
            [part.faces + off for part, off in zip(parts, offsets)], axis=0
        )
        colors = np.concatenate([p.colors for p in parts])
        return cls.create(vertices, faces, colors)

    @property
    def vertex_count(self) -> int:
        return int(len(self.vertices))

    @property
    def triangle_count(self) -> int:
        return int(len(self.faces))

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"MeshData(vertices={self.vertex_count}, "
            f"triangles={self.triangle_count})"
        )
