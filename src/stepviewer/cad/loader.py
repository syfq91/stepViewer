"""Turn a STEP file into triangles with cascadio, cached by file hash."""

from __future__ import annotations

import io
import logging
from pathlib import Path

import numpy as np

from ..config import MESH_ANGULAR_TOLERANCE, MESH_LINEAR_TOLERANCE
from . import cache
from .mesh import MeshData

log = logging.getLogger(__name__)

STEP_SUFFIXES = (".step", ".stp", ".p21")

#: OCCT's glTF writer normalises geometry to metres, which is what glTF expects.
#: The layout works in millimetres, so every imported model is scaled up.
#: The axis convention needs no fix-up: trimesh hands back Z-up geometry.
_GLB_UNIT_SCALE = 1000.0


class MeshLoadError(RuntimeError):
    """Raised when a STEP file cannot be tessellated."""


def load_mesh(
    path: str | Path,
    tolerance: float | None = None,
    use_cache: bool = True,
) -> MeshData:
    """Load a STEP file, reusing the disk cache when possible."""
    return load_mesh_with_sha1(path, tolerance, use_cache)[0]


def load_mesh_with_sha1(
    path: str | Path,
    tolerance: float | None = None,
    use_cache: bool = True,
) -> tuple[MeshData, str]:
    """Load a STEP file and also report the SHA-1 of its bytes."""
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(str(source))

    tolerance = MESH_LINEAR_TOLERANCE if tolerance is None else float(tolerance)
    source_sha1 = cache.file_sha1(source)

    if use_cache:
        cached = cache.read(source_sha1, tolerance)
        if cached is not None:
            log.debug("mesh cache hit for %s", source)
            return cached, source_sha1

    mesh = _mesh_from_step(source, tolerance)

    if use_cache:
        cache.write(source_sha1, tolerance, mesh)
    return mesh, source_sha1


def _mesh_from_step(path: Path, tolerance: float) -> MeshData:
    try:
        import cascadio
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise MeshLoadError(
            "cascadio is not installed; run 'pip install cascadio'"
        ) from exc

    try:
        glb = cascadio.load(
            path.read_bytes(),
            file_type="step",
            tol_linear=tolerance,
            tol_angular=MESH_ANGULAR_TOLERANCE,
            merge_primitives=True,
            use_parallel=True,
        )
    except Exception as exc:
        raise MeshLoadError(f"{path.name}: {exc}") from exc

    if not glb:
        raise MeshLoadError(f"{path.name}: no geometry could be tessellated")

    return _mesh_from_glb(glb, path.name)


def _mesh_from_glb(glb: bytes, label: str = "model") -> MeshData:
    import trimesh

    try:
        scene = trimesh.load(io.BytesIO(glb), file_type="glb", force="scene")
    except Exception as exc:
        raise MeshLoadError(f"{label}: unreadable GLB payload ({exc})") from exc

    parts: list[MeshData] = []
    for node in scene.graph.nodes_geometry:
        transform, geometry_name = scene.graph[node]
        geometry = scene.geometry.get(geometry_name)
        if geometry is None or len(getattr(geometry, "faces", ())) == 0:
            continue
        vertices = trimesh.transform_points(np.asarray(geometry.vertices), transform)
        parts.append(
            MeshData.create(
                vertices * _GLB_UNIT_SCALE,
                geometry.faces,
                _part_colors(geometry),
            )
        )

    if not parts:
        raise MeshLoadError(f"{label}: the file contains no solids")

    return MeshData.combined(parts)


def _part_colors(geometry) -> np.ndarray | None:
    """Per-vertex RGBA taken from the part material, if it has one."""
    visual = getattr(geometry, "visual", None)
    if visual is None:
        return None

    vertex_colors = getattr(visual, "vertex_colors", None)
    if vertex_colors is not None and len(vertex_colors) == len(geometry.vertices):
        return np.asarray(vertex_colors, dtype=np.uint8)

    material = getattr(visual, "material", None)
    base = getattr(material, "baseColorFactor", None)
    if base is not None and len(base) >= 3:
        return np.tile(_rgba_from_base(base), (len(geometry.vertices), 1))
    return None


def _rgba_from_base(base) -> np.ndarray:
    values = np.asarray(base, dtype=np.float64).ravel()
    if values.size == 3:
        values = np.append(values, 255.0)
    values = values[:4]
    if values.max(initial=0.0) <= 1.0:
        values = values * 255.0
    return np.clip(values, 0, 255).astype(np.uint8)
