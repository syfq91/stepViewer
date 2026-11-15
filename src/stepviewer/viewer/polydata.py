"""Convert numpy geometry into VTK datasets."""

from __future__ import annotations

import numpy as np
from vtkmodules.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
from vtkmodules.vtkCommonCore import VTK_UNSIGNED_CHAR, vtkPoints
from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData


def _cell_array(cells: np.ndarray, per_cell: int) -> vtkCellArray:
    """Build a cell array from an ``(n, per_cell)`` connectivity table."""
    table = np.empty((len(cells), per_cell + 1), dtype=np.int64)
    table[:, 0] = per_cell
    table[:, 1:] = cells
    array = vtkCellArray()
    array.SetCells(len(cells), numpy_to_vtkIdTypeArray(table.ravel(), deep=True))
    return array


def mesh_to_polydata(mesh) -> vtkPolyData:
    """Triangles plus per-vertex RGBA colours."""
    points = vtkPoints()
    points.SetData(numpy_to_vtk(np.ascontiguousarray(mesh.vertices), deep=True))

    poly = vtkPolyData()
    poly.SetPoints(points)
    poly.SetPolys(_cell_array(np.ascontiguousarray(mesh.faces), 3))

    colors = numpy_to_vtk(
        np.ascontiguousarray(mesh.colors), deep=True, array_type=VTK_UNSIGNED_CHAR
    )
    colors.SetName("Colors")
    poly.GetPointData().SetScalars(colors)
    return poly


def lines_polydata(segments: np.ndarray) -> vtkPolyData:
    """Build line cells from an ``(n, 2, 3)`` array of segment endpoints."""
    segment_data = np.asarray(segments, dtype=np.float64).reshape(-1, 2, 3)

    points = vtkPoints()
    points.SetData(
        numpy_to_vtk(np.ascontiguousarray(segment_data.reshape(-1, 3)), deep=True)
    )

    indices = np.arange(0, 2 * len(segment_data), 2, dtype=np.int64)
    lines = _cell_array(np.stack((indices, indices + 1), axis=1), 2)

    poly = vtkPolyData()
    poly.SetPoints(points)
    poly.SetLines(lines)
    return poly
