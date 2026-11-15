"""Plan (orthographic, top-down) and perspective cameras for one renderer."""

from __future__ import annotations

import numpy as np

PLAN = "plan"
PERSPECTIVE = "perspective"

#: Distance from the floor at which the orthographic camera is parked.
_PLAN_HEIGHT = 100_000.0
_MIN_PARALLEL_SCALE = 10.0
_MAX_PARALLEL_SCALE = 5_000_000.0


class CameraController:
    """Switches the renderer camera between the two layout views."""

    def __init__(self, renderer) -> None:
        self._renderer = renderer
        self._camera = renderer.GetActiveCamera()
        self.mode = PERSPECTIVE
        self._saved: dict[str, dict] = {}
        self.configure_default()

    # ------------------------------------------------------------------ modes
    def set_mode(self, mode: str) -> None:
        if mode not in (PLAN, PERSPECTIVE):
            raise ValueError(f"unknown view mode: {mode!r}")
        if mode == self.mode:
            return
        self._saved[self.mode] = self._snapshot()
        self.mode = mode
        saved = self._saved.get(mode)
        if saved is None:
            self.configure_default()
        else:
            self._restore(saved)

    def configure_default(self) -> None:
        if self.mode == PLAN:
            self._camera.SetParallelProjection(True)
            self._camera.SetViewUp(0.0, 1.0, 0.0)
            self._camera.SetFocalPoint(0.0, 0.0, 0.0)
            self._camera.SetPosition(0.0, 0.0, _PLAN_HEIGHT)
            self._camera.SetParallelScale(5000.0)
        else:
            self._camera.SetParallelProjection(False)
            self._camera.SetViewUp(0.0, 0.0, 1.0)
            self._camera.SetFocalPoint(0.0, 0.0, 0.0)
            self._camera.SetPosition(8000.0, -9000.0, 7000.0)
            self._camera.SetViewAngle(40.0)
        self._renderer.ResetCameraClippingRange()

    # -------------------------------------------------------------------- fit
    def fit(self, bounds: tuple[np.ndarray, np.ndarray] | None) -> None:
        low, high = bounds if bounds is not None else (np.zeros(3), np.full(3, 5000.0))
        low = np.asarray(low, dtype=np.float64)
        high = np.asarray(high, dtype=np.float64)
        centre = (low + high) * 0.5
        size = np.maximum(high - low, 1.0)

        if self.mode == PLAN:
            width, height = float(size[0]), float(size[1])
            aspect = self._aspect()
            scale = max(height * 0.5, width * 0.5 / aspect) * 1.2
            self._camera.SetParallelProjection(True)
            self._camera.SetViewUp(0.0, 1.0, 0.0)
            self._camera.SetFocalPoint(centre[0], centre[1], 0.0)
            self._camera.SetPosition(centre[0], centre[1], _PLAN_HEIGHT)
            self._camera.SetParallelScale(
                float(np.clip(scale, _MIN_PARALLEL_SCALE, _MAX_PARALLEL_SCALE))
            )
        else:
            radius = float(np.linalg.norm(size)) * 0.5
            direction = np.array([0.75, -1.0, 0.6])
            direction /= np.linalg.norm(direction)
            distance = radius / np.tan(np.radians(self._camera.GetViewAngle() * 0.5)) * 1.15
            self._camera.SetParallelProjection(False)
            self._camera.SetViewUp(0.0, 0.0, 1.0)
            self._camera.SetFocalPoint(*centre)
            self._camera.SetPosition(*(centre + direction * distance))
        self._renderer.ResetCameraClippingRange()

    # ------------------------------------------------------- screen <-> world
    def world_per_pixel(self) -> float:
        _, height = self._viewport_size()
        if height <= 0:
            return 1.0
        return 2.0 * float(self._camera.GetParallelScale()) / float(height)

    def display_to_world(self, x: float, y: float) -> tuple[float, float]:
        """Map a plan-view display position onto the floor plane."""
        width, height = self._viewport_size()
        scale = self.world_per_pixel()
        focal = self._camera.GetFocalPoint()
        return (
            float(focal[0] + (x - width * 0.5) * scale),
            float(focal[1] + (y - height * 0.5) * scale),
        )

    def pan(self, dx: float, dy: float) -> None:
        scale = self.world_per_pixel()
        position = self._camera.GetPosition()
        focal = self._camera.GetFocalPoint()
        offset = (-dx * scale, -dy * scale, 0.0)
        self._camera.SetPosition(position[0] + offset[0], position[1] + offset[1], position[2])
        self._camera.SetFocalPoint(focal[0] + offset[0], focal[1] + offset[1], focal[2])
        self._renderer.ResetCameraClippingRange()

    def zoom(self, factor: float) -> None:
        if self.mode == PLAN:
            scale = float(self._camera.GetParallelScale()) * factor
            self._camera.SetParallelScale(
                float(np.clip(scale, _MIN_PARALLEL_SCALE, _MAX_PARALLEL_SCALE))
            )
        else:
            self._camera.Dolly(factor)
        self._renderer.ResetCameraClippingRange()

    # ----------------------------------------------------------------- internals
    def _viewport_size(self) -> tuple[int, int]:
        window = self._renderer.GetRenderWindow()
        if window is None:
            return 1, 1
        width, height = window.GetSize()
        return max(int(width), 1), max(int(height), 1)

    def _aspect(self) -> float:
        width, height = self._viewport_size()
        return width / height if height else 1.0

    def _snapshot(self) -> dict:
        camera = self._camera
        return {
            "position": camera.GetPosition(),
            "focal": camera.GetFocalPoint(),
            "up": camera.GetViewUp(),
            "parallel": camera.GetParallelProjection(),
            "parallel_scale": camera.GetParallelScale(),
            "view_angle": camera.GetViewAngle(),
        }

    def _restore(self, state: dict) -> None:
        camera = self._camera
        camera.SetParallelProjection(state["parallel"])
        camera.SetViewUp(*state["up"])
        camera.SetFocalPoint(*state["focal"])
        camera.SetPosition(*state["position"])
        camera.SetParallelScale(state["parallel_scale"])
        camera.SetViewAngle(state["view_angle"])
        self._renderer.ResetCameraClippingRange()
