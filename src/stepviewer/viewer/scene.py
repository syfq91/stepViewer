"""The rendered scene: floor grid, one actor per item, selection highlight."""

from __future__ import annotations

import numpy as np
from vtkmodules.vtkCommonDataModel import vtkPolyData
from vtkmodules.vtkCommonTransforms import vtkTransform
from vtkmodules.vtkFiltersSources import vtkOutlineSource
from vtkmodules.vtkRenderingCore import (
    vtkActor,
    vtkCellPicker,
    vtkPolyDataMapper,
    vtkRenderer,
)

from ..config import BACKGROUND_COLOR, GRID_AXIS_COLOR, GRID_COLOR, SELECTION_COLOR
from ..core.transform import bounds_corners
from .guides import GuideLayer
from .polydata import lines_polydata, mesh_to_polydata

GRID_Z = -0.5
_SELECTION_PAD = 5.0


def _rgb(hex_color: str) -> tuple[float, float, float]:
    text = hex_color.lstrip("#")
    return tuple(int(text[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


def _address(vtk_object) -> str:
    """Stable key for a VTK object across separate Python wrappers."""
    return vtk_object.GetAddressAsString("")


class SceneView:
    """Owns every VTK prop and knows nothing about Qt."""

    def __init__(self, renderer: vtkRenderer) -> None:
        self._renderer = renderer
        self._actors: dict[str, vtkActor] = {}
        self._mappers: dict[str, vtkPolyDataMapper] = {}
        self._transforms: dict[str, vtkTransform] = {}
        self._local_bounds: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self._actor_ids: dict[str, str] = {}
        self._polydata_cache: dict[int, tuple[object, vtkPolyData]] = {}
        self._selection: list[str] = []
        self._grid_key: tuple[float, float] | None = None
        self._grid_actors: list[vtkActor] = []

        self._picker = vtkCellPicker()
        self._picker.SetTolerance(0.005)

        renderer.SetBackground(*_rgb(BACKGROUND_COLOR))
        self.guides = GuideLayer(renderer)
        self._create_highlight()

    # ------------------------------------------------------------------ items
    @property
    def renderer(self) -> vtkRenderer:
        return self._renderer

    def item_ids(self) -> list[str]:
        return list(self._actors)

    def add_item(self, item) -> None:
        if item.id in self._actors:
            self.update_item(item)
            return

        mapper = vtkPolyDataMapper()
        mapper.SetInputData(self._polydata_for(item.mesh))
        mapper.SetScalarModeToUsePointData()
        mapper.ScalarVisibilityOn()

        actor = vtkActor()
        actor.SetMapper(mapper)
        properties = actor.GetProperty()
        properties.SetInterpolationToFlat()
        properties.SetAmbient(0.3)
        properties.SetDiffuse(0.75)
        properties.SetSpecular(0.15)
        properties.SetSpecularPower(25.0)

        transform = vtkTransform()
        actor.SetUserTransform(transform)

        self._renderer.AddActor(actor)
        self._actors[item.id] = actor
        self._mappers[item.id] = mapper
        self._transforms[item.id] = transform
        self._local_bounds[item.id] = (
            np.asarray(item.mesh.bounds[0], dtype=np.float64),
            np.asarray(item.mesh.bounds[1], dtype=np.float64),
        )
        self._actor_ids[_address(actor)] = item.id
        self.update_item(item)

    def update_item(self, item) -> None:
        actor = self._actors.get(item.id)
        if actor is None:
            self.add_item(item)
            return
        self.apply_placement(item.id, item.placement)
        actor.SetVisibility(bool(item.visible))
        self._apply_colour(item)
        self.refresh_selection()

    def apply_placement(self, item_id: str, placement) -> None:
        """Move the actor without touching the model (used while dragging)."""
        transform = self._transforms.get(item_id)
        if transform is None:
            return
        transform.Identity()
        transform.Translate(*placement.position)
        transform.RotateZ(placement.rotation_z)
        transform.Scale(placement.scale, placement.scale, placement.scale)
        self.refresh_selection()

    def remove_item(self, item_id: str) -> None:
        actor = self._actors.pop(item_id, None)
        if actor is None:
            return
        self._renderer.RemoveActor(actor)
        self._actor_ids.pop(_address(actor), None)
        self._mappers.pop(item_id, None)
        self._transforms.pop(item_id, None)
        self._local_bounds.pop(item_id, None)
        if item_id in self._selection:
            self._selection.remove(item_id)
            self.refresh_selection()

    def replace_all(self, items) -> None:
        for item_id in list(self._actors):
            self.remove_item(item_id)
        for item in items:
            self.add_item(item)
        self.set_selection([])

    def set_visible(self, item_id: str, visible: bool) -> None:
        actor = self._actors.get(item_id)
        if actor is not None:
            actor.SetVisibility(bool(visible))

    def _polydata_for(self, mesh) -> vtkPolyData:
        key = id(mesh)
        cached = self._polydata_cache.get(key)
        if cached is not None and cached[0] is mesh:
            return cached[1]
        polydata = mesh_to_polydata(mesh)
        self._polydata_cache[key] = (mesh, polydata)
        return polydata

    def _apply_colour(self, item) -> None:
        actor = self._actors.get(item.id)
        mapper = self._mappers.get(item.id)
        if actor is None or mapper is None:
            return
        if item.color:
            mapper.ScalarVisibilityOff()
            actor.GetProperty().SetColor(*_rgb(item.color))
        else:
            mapper.ScalarVisibilityOn()
            actor.GetProperty().SetColor(1.0, 1.0, 1.0)

    # -------------------------------------------------------------- selection
    def set_selection(self, item_ids) -> None:
        self._selection = [item_id for item_id in item_ids if item_id in self._actors]
        self.refresh_selection()

    @property
    def selection(self) -> list[str]:
        return list(self._selection)

    def refresh_selection(self) -> None:
        if not self._selection:
            self._outline_actor.SetVisibility(False)
            self._footprint_actor.SetVisibility(False)
            return

        lows, highs = zip(*(self._world_bounds(item_id) for item_id in self._selection))
        low = np.min(lows, axis=0) - _SELECTION_PAD
        high = np.max(highs, axis=0) + _SELECTION_PAD

        self._outline_source.SetBounds(
            low[0], high[0], low[1], high[1], low[2], high[2]
        )
        self._outline_source.Update()
        self._outline_actor.SetVisibility(True)

        # A flat rectangle at floor level reads well in the plan view.
        self._footprint_source.SetBounds(low[0], high[0], low[1], high[1], 0.5, 3.0)
        self._footprint_source.Update()
        self._footprint_actor.SetVisibility(True)

    def _world_bounds(self, item_id: str) -> tuple[np.ndarray, np.ndarray]:
        low, high = self._local_bounds[item_id]
        transform = self._transforms[item_id]
        points = np.asarray(
            [
                transform.TransformDoublePoint(float(x), float(y), float(z))
                for x, y, z in bounds_corners(low, high)
            ]
        )
        return points.min(axis=0), points.max(axis=0)

    def selection_bounds(self) -> tuple[np.ndarray, np.ndarray] | None:
        if not self._selection:
            return None
        lows, highs = zip(*(self._world_bounds(item_id) for item_id in self._selection))
        return np.min(lows, axis=0), np.max(highs, axis=0)

    def _create_highlight(self) -> None:
        color = _rgb(SELECTION_COLOR)

        self._outline_source = vtkOutlineSource()
        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(self._outline_source.GetOutputPort())
        self._outline_actor = vtkActor()
        self._outline_actor.SetMapper(mapper)
        self._outline_actor.PickableOff()
        self._outline_actor.SetVisibility(False)
        properties = self._outline_actor.GetProperty()
        properties.SetColor(*color)
        properties.SetLineWidth(2.0)
        properties.SetLighting(False)
        self._renderer.AddActor(self._outline_actor)

        self._footprint_source = vtkOutlineSource()
        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(self._footprint_source.GetOutputPort())
        self._footprint_actor = vtkActor()
        self._footprint_actor.SetMapper(mapper)
        self._footprint_actor.PickableOff()
        self._footprint_actor.SetVisibility(False)
        properties = self._footprint_actor.GetProperty()
        properties.SetColor(*color)
        properties.SetLineWidth(1.5)
        properties.SetLighting(False)
        self._renderer.AddActor(self._footprint_actor)

    # ----------------------------------------------------------------- picking
    def pick(self, x: int, y: int) -> str | None:
        self._picker.Pick(float(x), float(y), 0.0, self._renderer)
        actor = self._picker.GetActor()
        if actor is None:
            return None
        return self._actor_ids.get(_address(actor))

    # -------------------------------------------------------------------- grid
    def update_grid(self, size: float, extent: float, visible: bool) -> None:
        key = (round(float(size), 6), round(float(extent), 6))
        if key != self._grid_key:
            self._build_grid(size, extent)
            self._grid_key = key
        for actor in self._grid_actors:
            actor.SetVisibility(bool(visible))

    def _build_grid(self, size: float, extent: float) -> None:
        for actor in self._grid_actors:
            self._renderer.RemoveActor(actor)
        self._grid_actors.clear()

        if size > 0 and extent > 0:
            steps = int(round(extent / size))
            if 1 <= steps <= 2000:
                coordinates = np.arange(-steps, steps + 1, dtype=np.float64) * size
                segments = []
                for value in coordinates:
                    if abs(value) < 1e-9:
                        continue
                    segments.append([[value, -extent, GRID_Z], [value, extent, GRID_Z]])
                    segments.append([[-extent, value, GRID_Z], [extent, value, GRID_Z]])
                if segments:
                    self._grid_actors.append(
                        self._line_actor(np.asarray(segments), GRID_COLOR, 1.0)
                    )

        axes = np.asarray(
            [
                [[-extent, 0.0, GRID_Z], [extent, 0.0, GRID_Z]],
                [[0.0, -extent, GRID_Z], [0.0, extent, GRID_Z]],
            ],
            dtype=np.float64,
        )
        self._grid_actors.append(self._line_actor(axes, GRID_AXIS_COLOR, 2.0))

    def _line_actor(self, segments: np.ndarray, color: str, width: float) -> vtkActor:
        mapper = vtkPolyDataMapper()
        mapper.SetInputData(lines_polydata(segments))
        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.PickableOff()
        properties = actor.GetProperty()
        properties.SetColor(*_rgb(color))
        properties.SetLineWidth(width)
        properties.SetLighting(False)
        self._renderer.AddActor(actor)
        return actor
