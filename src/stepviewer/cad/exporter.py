"""Write the whole layout out as one STEP compound with world placements."""

from __future__ import annotations

import logging
import math
from pathlib import Path

from ..core.item import SceneItem
from ..core.transform import Placement

log = logging.getLogger(__name__)

_shape_cache: dict[str, object] = {}


class StepExportError(RuntimeError):
    """Raised when the layout cannot be written to STEP."""


def clear_shape_cache() -> None:
    _shape_cache.clear()


def _read_shape(path: str):
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader

    cached = _shape_cache.get(path)
    if cached is not None:
        return cached

    reader = STEPControl_Reader()
    status = reader.ReadFile(path)
    if status != IFSelect_RetDone:
        raise StepExportError(f"could not read {Path(path).name}")
    reader.TransferRoots()
    shape = reader.OneShape()
    _shape_cache[path] = shape
    return shape


def _trsf(placement: Placement):
    """Similarity transform equivalent to ``T * Rz * S``."""
    from OCP.gp import gp_Trsf

    angle = math.radians(placement.rotation_z)
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    scale = placement.scale
    x, y, z = placement.position

    trsf = gp_Trsf()
    trsf.SetValues(
        cos_a * scale,
        -sin_a * scale,
        0.0,
        x,
        sin_a * scale,
        cos_a * scale,
        0.0,
        y,
        0.0,
        0.0,
        scale,
        z,
    )
    return trsf


def export_step(items: list[SceneItem], path: str | Path) -> Path:
    """Write every item into a single STEP file, returning the written path."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
    from OCP.TopoDS import TopoDS_Builder, TopoDS_Compound

    if not items:
        raise StepExportError("there is nothing to export")

    builder = TopoDS_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)

    failures: list[str] = []
    written = 0
    for item in items:
        try:
            shape = _read_shape(item.source_path)
            placed = BRepBuilderAPI_Transform(shape, _trsf(item.placement), True).Shape()
            builder.Add(compound, placed)
            written += 1
        except Exception as exc:
            log.warning("skipping %s: %s", item.source_path, exc)
            failures.append(f"{Path(item.source_path).name}: {exc}")

    if written == 0:
        detail = "\n".join(failures) if failures else "no readable sources"
        raise StepExportError(f"nothing could be exported\n{detail}")

    target = Path(path)
    if target.suffix.lower() not in (".step", ".stp"):
        target = target.with_suffix(".step")

    writer = STEPControl_Writer()
    writer.Transfer(compound, STEPControl_AsIs)
    status = writer.Write(str(target))
    if status != IFSelect_RetDone:
        raise StepExportError(f"OpenCASCADE could not write {target}")

    log.info("wrote %d of %d items to %s", written, len(items), target)
    return target
