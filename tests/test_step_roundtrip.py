"""End-to-end checks that need the real CAD kernels (marked slow)."""

import numpy as np
import pytest

from stepviewer.cad.exporter import clear_shape_cache, export_step
from stepviewer.cad.loader import load_mesh
from stepviewer.core.project import Project
from stepviewer.core.transform import Placement

pytestmark = pytest.mark.slow


def test_step_import_preserves_size_and_up_axis(table_step):
    """The table fixture is 1200 x 800 x 750 mm; Z must be the 750 mm axis."""
    mesh = load_mesh(table_step, use_cache=False)
    low, high = mesh.bounds
    size = high - low
    assert size == pytest.approx((1200.0, 800.0, 750.0), abs=1.0)
    assert mesh.triangle_count > 0


def test_mesh_cache_round_trip(table_step):
    first = load_mesh(table_step)
    second = load_mesh(table_step)
    assert np.allclose(first.vertices, second.vertices)
    assert np.array_equal(first.faces, second.faces)


def test_export_bakes_world_placement_into_the_geometry(table_step, tmp_path):
    clear_shape_cache()
    mesh = load_mesh(table_step)
    project = Project()
    item = project.new_item(
        str(table_step),
        mesh,
        placement=Placement((1500.0, 400.0, 0.0), 90.0, 1.0),
    )
    project.insert_item(item)

    written = export_step(project.items, tmp_path / "layout.step")
    assert written.is_file()

    restored = load_mesh(written, use_cache=False)
    low, high = restored.bounds
    centre = (low + high) * 0.5

    # local centre (600, 400, 375) -> rotated 90 deg -> (-400, 600, 375)
    # -> translated -> (1100, 1000, 375)
    assert centre == pytest.approx((1100.0, 1000.0, 375.0), abs=2.0)


def test_export_scales_and_stacks_items(table_step, chair_step, tmp_path):
    clear_shape_cache()
    project = Project()
    project.insert_item(
        project.new_item(
            str(table_step),
            load_mesh(table_step),
            placement=Placement((0.0, 0.0, 0.0), 0.0, 2.0),
        )
    )
    project.insert_item(
        project.new_item(
            str(chair_step),
            load_mesh(chair_step),
            placement=Placement((5000.0, 0.0, 0.0), 0.0, 1.0),
        )
    )

    written = export_step(project.items, tmp_path / "combined.step")
    restored = load_mesh(written, use_cache=False)
    low, high = restored.bounds

    assert low[0] == pytest.approx(0.0, abs=2.0)
    assert high[0] == pytest.approx(5450.0, abs=2.0)
    # the doubled table is 1500 mm tall
    assert high[2] == pytest.approx(1500.0, abs=2.0)


def test_export_without_items_fails_cleanly(tmp_path):
    from stepviewer.cad.exporter import StepExportError

    with pytest.raises(StepExportError):
        export_step([], tmp_path / "empty.step")
