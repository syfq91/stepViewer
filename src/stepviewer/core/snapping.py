"""Grid snapping and edge/centre alignment, with no Qt or VTK dependencies."""

from __future__ import annotations

from dataclasses import dataclass

from .transform import Footprint


@dataclass(frozen=True)
class Guide:
    """A temporary alignment line shown while dragging."""

    axis: str  # "x" or "y"
    value: float
    span: tuple[float, float]  # extent along the perpendicular axis


@dataclass(frozen=True)
class SnapResult:
    xy: tuple[float, float]
    guides: tuple[Guide, ...] = ()
    snapped_x: bool = False
    snapped_y: bool = False


def snap_value(value: float, size: float) -> float:
    if size <= 0:
        return value
    return round(value / size) * size


def _edges(low: float, high: float) -> tuple[tuple[float, bool], ...]:
    """Candidate alignment values, flagged when they are the centre."""
    return ((low, False), (high, False), ((low + high) * 0.5, True))


def _tier(our_centre: bool, other_centre: bool) -> int:
    """Rank alignments: real edges beat centres, centres beat mixed pairs."""
    if not our_centre and not other_centre:
        return 0
    if our_centre and other_centre:
        return 1
    return 2


def _best_alignment(
    proposed: float,
    offsets: tuple[float, float],
    others: list[tuple[float, float]],
    threshold: float,
) -> tuple[float, float] | None:
    """Return ``(delta, matched_value)`` for the closest alignment, if any."""
    best: tuple[tuple[int, float], float, float] | None = None
    ours = _edges(proposed + offsets[0], proposed + offsets[1])

    for other_low, other_high in others:
        for other_value, other_centre in _edges(other_low, other_high):
            for our_value, our_centre in ours:
                delta = other_value - our_value
                if abs(delta) > threshold:
                    continue
                rank = (_tier(our_centre, other_centre), abs(delta))
                if best is None or rank < best[0]:
                    best = (rank, delta, other_value)

    if best is None:
        return None
    return best[1], best[2]


def snap_xy(
    proposed_xy: tuple[float, float],
    footprint_offset: Footprint,
    other_footprints: list[Footprint],
    grid_size: float,
    threshold: float,
    grid_enabled: bool = True,
    item_snap_enabled: bool = True,
) -> SnapResult:
    """Snap a proposed item position to the grid and to nearby items.

    ``footprint_offset`` is the item's footprint relative to its position, so
    the returned ``xy`` is the new position.
    """
    px, py = float(proposed_xy[0]), float(proposed_xy[1])
    if grid_enabled:
        px, py = snap_value(px, grid_size), snap_value(py, grid_size)

    off_low_x, off_low_y, off_high_x, off_high_y = footprint_offset

    x_match = y_match = None
    if item_snap_enabled and other_footprints:
        if threshold > 0:
            x_match = _best_alignment(
                px, (off_low_x, off_high_x), [(f[0], f[2]) for f in other_footprints], threshold
            )
            y_match = _best_alignment(
                py, (off_low_y, off_high_y), [(f[1], f[3]) for f in other_footprints], threshold
            )
        if x_match is not None:
            px += x_match[0]
        if y_match is not None:
            py += y_match[0]

    final: Footprint = (
        px + off_low_x,
        py + off_low_y,
        px + off_high_x,
        py + off_high_y,
    )

    guides: list[Guide] = []
    if x_match is not None:
        value = x_match[1]
        span = _span_perpendicular(other_footprints, final, axis="x", value=value)
        guides.append(Guide("x", float(value), span))
    if y_match is not None:
        value = y_match[1]
        span = _span_perpendicular(other_footprints, final, axis="y", value=value)
        guides.append(Guide("y", float(value), span))

    return SnapResult(
        xy=(px, py),
        guides=tuple(guides),
        snapped_x=x_match is not None,
        snapped_y=y_match is not None,
    )


def _span_perpendicular(
    others: list[Footprint], final: Footprint, axis: str, value: float
) -> tuple[float, float]:
    """Length of the guide line, covering the dragged item and its neighbours."""
    if axis == "x":
        span_low, span_high = final[1], final[3]
        for footprint in others:
            if abs(footprint[0] - value) < 1e-6 or abs(footprint[2] - value) < 1e-6 or abs(
                (footprint[0] + footprint[2]) * 0.5 - value
            ) < 1e-6:
                span_low = min(span_low, footprint[1])
                span_high = max(span_high, footprint[3])
    else:
        span_low, span_high = final[0], final[2]
        for footprint in others:
            if abs(footprint[1] - value) < 1e-6 or abs(footprint[3] - value) < 1e-6 or abs(
                (footprint[1] + footprint[3]) * 0.5 - value
            ) < 1e-6:
                span_low = min(span_low, footprint[0])
                span_high = max(span_high, footprint[2])
    return float(span_low), float(span_high)
