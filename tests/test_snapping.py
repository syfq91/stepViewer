import pytest

from stepviewer.core.snapping import snap_value, snap_xy

OFFSET = (0.0, 0.0, 1000.0, 600.0)  # 1000 x 600 box with its origin at the corner
OTHER = (1950.0, 0.0, 2950.0, 600.0)  # deliberately off-grid neighbour


def test_snap_value_rounds_to_the_nearest_grid_line():
    assert snap_value(149.0, 100.0) == pytest.approx(100.0)
    assert snap_value(151.0, 100.0) == pytest.approx(200.0)
    assert snap_value(-149.0, 100.0) == pytest.approx(-100.0)


def test_snap_value_with_zero_size_is_a_no_op():
    assert snap_value(123.456, 0.0) == pytest.approx(123.456)


def test_grid_snap_only():
    result = snap_xy((1234.0, 567.0), OFFSET, [], 100.0, 80.0)
    assert result.xy == pytest.approx((1200.0, 600.0))
    assert result.guides == ()
    assert not result.snapped_x and not result.snapped_y


def test_grid_snap_can_be_disabled():
    result = snap_xy((1234.0, 567.0), OFFSET, [], 100.0, 80.0, grid_enabled=False)
    assert result.xy == pytest.approx((1234.0, 567.0))


def test_item_edges_snap_together():
    # Grid snapping alone leaves the dragged item at x=900, whose right edge is
    # 1950 - 1900 = 50 mm short of the neighbour. That is inside the threshold,
    # so the edges should end up flush at x=950.
    result = snap_xy((940.0, 0.0), OFFSET, [OTHER], 100.0, 80.0)
    assert result.xy[0] == pytest.approx(950.0)
    assert result.snapped_x
    assert result.guides[0].axis == "x"
    assert result.guides[0].value == pytest.approx(1950.0)


def test_alignment_outside_the_threshold_keeps_the_grid_position():
    result = snap_xy((700.0, 0.0), OFFSET, [OTHER], 100.0, 80.0)
    assert result.xy[0] == pytest.approx(700.0)
    assert not result.snapped_x


def test_axes_are_snapped_independently():
    neighbour = (1950.0, 2950.0, 2950.0, 3550.0)
    result = snap_xy((940.0, 2940.0), OFFSET, [neighbour], 100.0, 80.0)
    assert result.xy[0] == pytest.approx(950.0)
    assert result.xy[1] == pytest.approx(2950.0)
    assert {guide.axis for guide in result.guides} == {"x", "y"}


def test_centre_alignment_is_used_when_no_edge_is_close():
    # Neighbour centre x = 1400; the dragged item's centre would be 1370.
    neighbour = (1300.0, 0.0, 1500.0, 600.0)
    result = snap_xy((870.0, 0.0), OFFSET, [neighbour], 100.0, 80.0, grid_enabled=False)
    assert result.xy[0] == pytest.approx(900.0)
    assert result.snapped_x


def test_guide_span_covers_both_items():
    result = snap_xy((940.0, 0.0), OFFSET, [OTHER], 100.0, 80.0)
    span_low, span_high = result.guides[0].span
    assert span_low <= 0.0
    assert span_high >= 600.0


def test_item_snapping_can_be_disabled():
    result = snap_xy(
        (940.0, 0.0), OFFSET, [OTHER], 100.0, 80.0, item_snap_enabled=False
    )
    assert result.xy[0] == pytest.approx(900.0)
    assert not result.snapped_x
