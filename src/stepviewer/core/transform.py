"""Placement maths: every item is positioned by ``M = T * Rz * S``."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

Vec3 = tuple[float, float, float]
Footprint = tuple[float, float, float, float]

_CORNER_SIGNS = np.array(
    [
        [0, 0, 0],
        [1, 0, 0],
        [1, 1, 0],
        [0, 1, 0],
        [0, 0, 1],
        [1, 0, 1],
        [1, 1, 1],
        [0, 1, 1],
    ],
    dtype=bool,
)


def placement_matrix(
    position: Vec3, rotation_z_deg: float, scale: float = 1.0
) -> np.ndarray:
    """Return the 4x4 local-to-world matrix for a placement."""
    angle = math.radians(rotation_z_deg)
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, 0] = (cos_a * scale, sin_a * scale, 0.0)
    matrix[:3, 1] = (-sin_a * scale, cos_a * scale, 0.0)
    matrix[:3, 2] = (0.0, 0.0, scale)
    matrix[:3, 3] = position
    return matrix


def transform_points(matrix: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Apply a 4x4 matrix to an ``(N, 3)`` array of points."""
    array = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    return array @ matrix[:3, :3].T + matrix[:3, 3]


def bounds_corners(low: np.ndarray, high: np.ndarray) -> np.ndarray:
    """Return the eight corners of an axis aligned box as ``(8, 3)``."""
    low = np.asarray(low, dtype=np.float64)
    high = np.asarray(high, dtype=np.float64)
    return np.where(_CORNER_SIGNS, high, low)


def bounds_of(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(low, high)`` for an ``(N, 3)`` point array."""
    array = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    if array.size == 0:
        raise ValueError("cannot compute bounds of an empty point array")
    return array.min(axis=0), array.max(axis=0)


def footprint_of(
    low: np.ndarray, high: np.ndarray, placement: "Placement", translate: bool = True
) -> Footprint:
    """Return the world XY footprint ``(min_x, min_y, max_x, max_y)`` of a box."""
    origin = placement.position if translate else (0.0, 0.0, 0.0)
    matrix = placement_matrix(origin, placement.rotation_z, placement.scale)
    projected = transform_points(matrix, bounds_corners(low, high))
    return (
        float(projected[:, 0].min()),
        float(projected[:, 1].min()),
        float(projected[:, 0].max()),
        float(projected[:, 1].max()),
    )


@dataclass(frozen=True)
class Placement:
    """Where an item sits: translation, rotation about Z, uniform scale."""

    position: Vec3 = (0.0, 0.0, 0.0)
    rotation_z: float = 0.0
    scale: float = 1.0

    def matrix(self) -> np.ndarray:
        return placement_matrix(self.position, self.rotation_z, self.scale)

    @property
    def xy(self) -> tuple[float, float]:
        return float(self.position[0]), float(self.position[1])

    def moved_to_xy(self, x: float, y: float) -> "Placement":
        return Placement((float(x), float(y), float(self.position[2])), self.rotation_z, self.scale)

    def rotated_by(self, degrees: float) -> "Placement":
        rotation = (self.rotation_z + degrees) % 360.0
        return Placement(self.position, rotation, self.scale)

    def with_z(self, z: float) -> "Placement":
        return Placement((self.position[0], self.position[1], float(z)), self.rotation_z, self.scale)

    def with_scale(self, scale: float) -> "Placement":
        return Placement(self.position, self.rotation_z, float(scale))
