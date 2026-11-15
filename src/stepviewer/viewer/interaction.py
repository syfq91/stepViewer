"""VTK interactor styles: manual gestures for the plan view, orbiting for 3D."""

from __future__ import annotations

from vtkmodules.vtkInteractionStyle import (
    vtkInteractorStyleTrackballCamera,
    vtkInteractorStyleUser,
)

#: Maximum pointer travel, in pixels, that still counts as a click.
_CLICK_SLOP = 4


class PlanInteractor(vtkInteractorStyleUser):
    """Takes every gesture and forwards it to a handler.

    ``vtkInteractorStyleUser`` performs no camera manipulation of its own, which
    is exactly what the plan view needs: the left button drags items, the middle
    button pans, and the wheel zooms, all implemented by the handler.
    """

    def __init__(self, interactor, handler) -> None:
        super().__init__()
        self._interactor = interactor
        self._handler = handler

        self.AddObserver("LeftButtonPressEvent", self._left_down)
        self.AddObserver("LeftButtonReleaseEvent", self._left_up)
        self.AddObserver("MiddleButtonPressEvent", self._middle_down)
        self.AddObserver("MiddleButtonReleaseEvent", self._middle_up)
        self.AddObserver("RightButtonPressEvent", self._right_down)
        self.AddObserver("RightButtonReleaseEvent", self._right_up)
        self.AddObserver("MouseMoveEvent", self._move)
        self.AddObserver("MouseWheelForwardEvent", self._wheel_forward)
        self.AddObserver("MouseWheelBackwardEvent", self._wheel_backward)

    # ------------------------------------------------------------------ events
    def _left_down(self, _obj, _event) -> None:
        self._handler.press(*self._position(), "left", *self._modifiers())

    def _left_up(self, _obj, _event) -> None:
        self._handler.release(*self._position(), "left", *self._modifiers())

    def _middle_down(self, _obj, _event) -> None:
        self._handler.press(*self._position(), "middle", *self._modifiers())

    def _middle_up(self, _obj, _event) -> None:
        self._handler.release(*self._position(), "middle", *self._modifiers())

    def _right_down(self, _obj, _event) -> None:
        self._handler.press(*self._position(), "right", *self._modifiers())

    def _right_up(self, _obj, _event) -> None:
        self._handler.release(*self._position(), "right", *self._modifiers())

    def _move(self, _obj, _event) -> None:
        self._handler.move(*self._position(), *self._modifiers())

    def _wheel_forward(self, _obj, _event) -> None:
        self._handler.wheel(1, *self._position(), *self._modifiers())

    def _wheel_backward(self, _obj, _event) -> None:
        self._handler.wheel(-1, *self._position(), *self._modifiers())

    # --------------------------------------------------------------- internals
    def _position(self) -> tuple[int, int]:
        x, y = self._interactor.GetEventPosition()
        return int(x), int(y)

    def _modifiers(self) -> tuple[bool, bool]:
        return bool(self._interactor.GetShiftKey()), bool(self._interactor.GetControlKey())


def make_orbit_style() -> vtkInteractorStyleTrackballCamera:
    return vtkInteractorStyleTrackballCamera()


def attach_click_picker(interactor, callback) -> None:
    """Call ``callback(x, y)`` for left clicks that did not turn into a drag."""

    pressed: dict[str, tuple[int, int] | None] = {"position": None}

    def on_press(obj, _event) -> None:
        pressed["position"] = obj.GetEventPosition()

    def on_release(obj, _event) -> None:
        start = pressed["position"]
        pressed["position"] = None
        if start is None:
            return
        x, y = obj.GetEventPosition()
        if abs(x - start[0]) <= _CLICK_SLOP and abs(y - start[1]) <= _CLICK_SLOP:
            callback(int(x), int(y))

    interactor.AddObserver("LeftButtonPressEvent", on_press)
    interactor.AddObserver("LeftButtonReleaseEvent", on_release)
