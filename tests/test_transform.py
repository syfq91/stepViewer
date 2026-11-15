import numpy as np
import pytest

from stepviewer.core.transform import (
    Placement,
    bounds_corners,
    bounds_of,
    footprint_of,
    placement_matrix,
    transform_points,
)


def test_identity_placement_leaves_points_alone():
    matrix = placement_matrix((0.0, 0.0, 0.0), 0.0, 1.0)
    points = np.array([[1.0, 2.0, 3.0]])
    assert np.allclose(transform_points(matrix, points), points)


def test_translation_is_applied():
    matrix = placement_matrix((10.0, -5.0, 2.0), 0.0, 1.0)
    assert np.allclose(transform_points(matrix, [[0.0, 0.0, 0.0]]), [[10.0, -5.0, 2.0]])


def test_rotation_of_ninety_degrees_about_z():
    matrix = placement_matrix((0.0, 0.0, 0.0), 90.0, 1.0)
    assert np.allclose(transform_points(matrix, [[1.0, 0.0, 0.0]]), [[0.0, 1.0, 0.0]])


def test_transform_order_is_translate_rotate_scale():
    matrix = placement_matrix((10.0, 0.0, 0.0), 90.0, 2.0)
    # scale first: (1,0,0) -> (2,0,0); rotate: (0,2,0); translate: (10,2,0)
    assert np.allclose(transform_points(matrix, [[1.0, 0.0, 0.0]]), [[10.0, 2.0, 0.0]])


def test_bounds_corners_cover_the_box():
    corners = bounds_corners(np.zeros(3), np.array([2.0, 3.0, 4.0]))
    assert corners.shape == (8, 3)
    low, high = bounds_of(corners)
    assert np.allclose(low, [0.0, 0.0, 0.0])
    assert np.allclose(high, [2.0, 3.0, 4.0])


def test_footprint_rotates_with_the_item():
    low, high = np.zeros(3), np.array([1000.0, 600.0, 750.0])
    footprint = footprint_of(low, high, Placement((0.0, 0.0, 0.0), 90.0, 1.0))
    assert footprint == pytest.approx((-600.0, 0.0, 0.0, 1000.0))


def test_footprint_offset_ignores_position():
    low, high = np.zeros(3), np.array([1000.0, 600.0, 750.0])
    placement = Placement((5000.0, -2000.0, 0.0), 0.0, 2.0)
    translated = footprint_of(low, high, placement)
    offset = footprint_of(low, high, placement, translate=False)
    assert translated[0] - offset[0] == pytest.approx(5000.0)
    assert translated[1] - offset[1] == pytest.approx(-2000.0)
    assert translated[2] - offset[2] == pytest.approx(5000.0)


def test_placement_helpers_preserve_other_components():
    placement = Placement((1.0, 2.0, 3.0), 45.0, 2.0)
    moved = placement.moved_to_xy(5.0, 6.0)
    assert moved.position == (5.0, 6.0, 3.0)
    assert moved.rotation_z == 45.0
    assert moved.scale == 2.0

    rotated = placement.rotated_by(30.0)
    assert rotated.rotation_z == 75.0

    wrapped = Placement(rotation_z=350.0).rotated_by(20.0)
    assert wrapped.rotation_z == pytest.approx(10.0)
