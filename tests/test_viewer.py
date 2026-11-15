import numpy as np
import pytest
from vtkmodules.vtkRenderingCore import vtkRenderer, vtkRenderWindow

from stepviewer.core.item import SceneItem
from stepviewer.core.transform import Placement
from stepviewer.viewer.camera import PERSPECTIVE, PLAN, CameraController
from stepviewer.viewer.polydata import lines_polydata, mesh_to_polydata
from stepviewer.viewer.scene import SceneView


@pytest.fixture
def renderer():
    """A renderer with a sized window, without ever rendering.

    ``yield`` keeps the render window alive for the duration of the test: a
    renderer does not own its window, and a collected window makes
    ``GetSize()`` meaningless.
    """
    window = vtkRenderWindow()
    window.SetSize(1000, 500)
    view = vtkRenderer()
    window.AddRenderer(view)
    yield view
    window.RemoveRenderer(view)


def make_item(box_mesh, placement=Placement()) -> SceneItem:
    return SceneItem(
        id="item-1",
        name="box",
        source_path="/models/box.step",
        mesh=box_mesh,
        placement=placement,
    )


# --------------------------------------------------------------------- polydata
def test_mesh_to_polydata_preserves_counts_and_colors(box_mesh):
    polydata = mesh_to_polydata(box_mesh)
    assert polydata.GetNumberOfPoints() == box_mesh.vertex_count
    assert polydata.GetNumberOfPolys() == box_mesh.triangle_count
    colors = polydata.GetPointData().GetScalars()
    assert colors is not None
    assert colors.GetNumberOfComponents() == 4


def test_lines_polydata_builds_segments():
    segments = np.array(
        [[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0]]]
    )
    polydata = lines_polydata(segments)
    assert polydata.GetNumberOfPoints() == 4
    assert polydata.GetNumberOfLines() == 2


# ----------------------------------------------------------------------- camera
def test_plan_camera_centre_maps_to_the_view_centre(renderer):
    camera = CameraController(renderer)
    camera.set_mode(PLAN)
    camera.fit((np.array([-1000.0, -500.0, 0.0]), np.array([1000.0, 500.0, 100.0])))
    assert camera.display_to_world(500, 250) == pytest.approx((0.0, 0.0))


def test_plan_camera_display_scale_matches_parallel_scale(renderer):
    camera = CameraController(renderer)
    camera.set_mode(PLAN)
    camera.fit((np.array([-1000.0, -500.0, 0.0]), np.array([1000.0, 500.0, 100.0])))

    scale = camera.world_per_pixel()
    # 2000 x 1000 bounds in a 1000 x 500 window -> scale = 500 * 1.2, over 500 px
    assert scale == pytest.approx(2.4)
    assert camera.display_to_world(600, 250) == pytest.approx((240.0, 0.0))
    assert camera.display_to_world(500, 350) == pytest.approx((0.0, 240.0))


def test_camera_modes_keep_their_own_state(renderer):
    camera = CameraController(renderer)
    camera.set_mode(PLAN)
    camera.fit((np.array([0.0, 0.0, 0.0]), np.array([4000.0, 2000.0, 100.0])))
    plan_scale = camera._camera.GetParallelScale()

    camera.set_mode(PERSPECTIVE)
    assert camera._camera.GetParallelProjection() == 0

    camera.set_mode(PLAN)
    assert camera._camera.GetParallelProjection() == 1
    assert camera._camera.GetParallelScale() == pytest.approx(plan_scale)


def test_zoom_changes_parallel_scale_in_plan_view(renderer):
    camera = CameraController(renderer)
    camera.set_mode(PLAN)
    before = camera._camera.GetParallelScale()
    camera.zoom(0.5)
    assert camera._camera.GetParallelScale() == pytest.approx(before * 0.5)


# ------------------------------------------------------------------------ scene
def test_scene_tracks_items_and_selection(renderer, box_mesh):
    scene = SceneView(renderer)
    item = make_item(box_mesh, Placement((100.0, 50.0, 0.0), 90.0, 1.0))

    scene.add_item(item)
    assert scene.item_ids() == [item.id]

    scene.set_selection([item.id])
    low, high = scene.selection_bounds()
    # local box 1000 x 600 x 750, rotated 90 deg about the origin, then moved
    assert low == pytest.approx((-500.0, 50.0, 0.0), abs=1.0)
    assert high == pytest.approx((100.0, 1050.0, 750.0), abs=1.0)

    scene.remove_item(item.id)
    assert scene.item_ids() == []
    assert scene.selection == []


def test_scene_follows_a_live_placement(renderer, box_mesh):
    scene = SceneView(renderer)
    item = make_item(box_mesh)
    scene.add_item(item)
    scene.set_selection([item.id])

    scene.apply_placement(item.id, Placement((2000.0, 0.0, 0.0)))
    low, high = scene.selection_bounds()
    # The model still holds the old placement; the actor moved on its own.
    assert item.placement.position == (0.0, 0.0, 0.0)
    assert high[0] - low[0] == pytest.approx(1000.0, abs=1.0)
    assert low[0] == pytest.approx(2000.0, abs=1.0)


def test_scene_hides_and_colours_items(renderer, box_mesh):
    scene = SceneView(renderer)
    item = make_item(box_mesh)
    scene.add_item(item)

    item.visible = False
    scene.update_item(item)
    assert scene._actors[item.id].GetVisibility() == 0

    item.visible = True
    item.color = "#ff0000"
    scene.update_item(item)
    assert scene._actors[item.id].GetVisibility() == 1
    assert scene._mappers[item.id].GetScalarVisibility() == 0


def test_grid_rebuilds_only_when_the_key_changes(renderer):
    scene = SceneView(renderer)
    scene.update_grid(100.0, 20000.0, True)
    first = list(scene._grid_actors)
    scene.update_grid(100.0, 20000.0, True)
    assert scene._grid_actors == first

    scene.update_grid(250.0, 20000.0, True)
    assert scene._grid_actors != first
