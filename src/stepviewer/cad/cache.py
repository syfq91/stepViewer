"""On-disk cache of tessellated meshes, keyed by source hash and tolerance."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from ..config import cache_dir
from .mesh import MeshData

#: Bump whenever the tessellation output changes meaning (units, axis, layout),
#: so existing entries are ignored instead of being read back as stale geometry.
CACHE_VERSION = 1


def file_sha1(path: str | Path) -> str:
    digest = hashlib.sha1()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cache_path(source_sha1: str, tolerance: float) -> Path:
    return cache_dir() / f"{source_sha1}-{tolerance:g}-v{CACHE_VERSION}.npz"


def read(source_sha1: str, tolerance: float) -> MeshData | None:
    path = cache_path(source_sha1, tolerance)
    if not path.is_file():
        return None
    try:
        with np.load(path) as data:
            return MeshData.create(data["vertices"], data["faces"], data["colors"])
    except Exception:
        # A truncated or stale cache entry is simply rebuilt.
        path.unlink(missing_ok=True)
        return None


def write(source_sha1: str, tolerance: float, mesh: MeshData) -> Path | None:
    path = cache_path(source_sha1, tolerance)
    try:
        np.savez_compressed(
            path,
            vertices=mesh.vertices,
            faces=mesh.faces,
            colors=mesh.colors,
        )
    except OSError:
        return None
    return path
