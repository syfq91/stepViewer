"""Alignment guide lines shown while dragging."""

from __future__ import annotations

import numpy as np
from vtkmodules.vtkRenderingCore import (
    vtkActor,
    vtkPolyDataMapper,
)

from ..config import GUIDE_COLOR
from .polydata import lines_polydata

#: Guides sit slightly above the floor so they are never hidden by the grid.
_GUIDE_Z = 1.0
_COLOUR = tuple(int(GUIDE_COLOR.lstrip("#")[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


class GuideLayer:
    def __init__(self, renderer) -> None:
        self._renderer = renderer
        self._mapper = vtkPolyDataMapper()
        self._actor = vtkActor()
        self._actor.SetMapper(self._mapper)
        self._actor.PickableOff()
        self._actor.SetVisibility(False)
        properties = self._actor.GetProperty()
        properties.SetColor(*_COLOUR)
        properties.SetLineWidth(2.0)
        properties.SetLighting(False)
        renderer.AddActor(self._actor)

    def show(self, guides) -> None:
        segments = []
        for guide in guides:
            if guide.axis == "x":
                segments.append(
                    [[guide.value, guide.span[0], _GUIDE_Z], [guide.value, guide.span[1], _GUIDE_Z]]
                )
            else:
                segments.append(
                    [[guide.span[0], guide.value, _GUIDE_Z], [guide.span[1], guide.value, _GUIDE_Z]]
                )
        if not segments:
            self.clear()
            return
        self._mapper.SetInputData(lines_polydata(np.asarray(segments, dtype=np.float64)))
        self._actor.SetVisibility(True)

    def clear(self) -> None:
        self._actor.SetVisibility(False)
