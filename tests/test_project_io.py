import json

import pytest

from stepviewer.core.project import (
    GridSettings,
    MissingSourceError,
    Project,
    ProjectFormatError,
)
from stepviewer.core.transform import Placement

SOURCE = "/models/table.step"


def make_project(box_mesh) -> Project:
    project = Project()
    project.grid = GridSettings(size=250.0, snap=False)
    item = project.new_item(
        SOURCE,
        box_mesh,
        source_sha1="abc123",
        placement=Placement((1500.0, 400.0, 0.0), 90.0, 2.0),
        name="Table",
    )
    project.insert_item(item)
    return project


def provider(mesh):
    def resolve(path: str, sha1: str):
        if path != SOURCE:
            raise MissingSourceError(path)
        return mesh

    return resolve


def test_round_trip_preserves_placement_and_grid(box_mesh):
    project = make_project(box_mesh)
    payload = project.to_dict()
    restored, problems = Project.from_dict(payload, provider(box_mesh))

    assert problems == []
    assert len(restored) == 1
    item = restored.items[0]
    assert item.name == "Table"
    assert item.placement.position == pytest.approx((1500.0, 400.0, 0.0))
    assert item.placement.rotation_z == pytest.approx(90.0)
    assert item.placement.scale == pytest.approx(2.0)
    assert item.source_sha1 == "abc123"
    assert restored.grid.size == pytest.approx(250.0)
    assert restored.grid.snap is False


def test_save_and_load_from_disk(box_mesh, tmp_path):
    project = make_project(box_mesh)
    written = project.save(tmp_path / "layout")
    assert written.suffix == ".svproj"
    assert written.is_file()
    assert json.loads(written.read_text())["format"] == "stepviewer-layout"

    loaded, problems = Project.load(written, provider(box_mesh))
    assert problems == []
    assert loaded.path == written
    assert loaded.items[0].placement.rotation_z == pytest.approx(90.0)


def test_missing_sources_are_reported_not_crashed(box_mesh):
    project = make_project(box_mesh)
    payload = project.to_dict()
    payload["items"].append(dict(payload["items"][0], id="missing-1", source="/nowhere/ghost.step"))

    restored, problems = Project.from_dict(payload, provider(box_mesh))
    assert len(restored) == 1
    assert problems and problems[0][0] == "/nowhere/ghost.step"


def test_unknown_format_is_rejected(box_mesh):
    with pytest.raises(ProjectFormatError):
        Project.from_dict({"format": "something-else", "items": []}, provider(box_mesh))


def test_newer_version_is_rejected(box_mesh):
    with pytest.raises(ProjectFormatError):
        Project.from_dict(
            {"format": "stepviewer-layout", "version": 99, "items": []},
            provider(box_mesh),
        )


def test_names_are_made_unique(box_mesh):
    project = Project()
    first = project.new_item(SOURCE, box_mesh, name="Chair")
    project.insert_item(first)
    second = project.new_item(SOURCE, box_mesh, name="Chair")
    assert second.name == "Chair 2"


def test_imports_are_placed_side_by_side(box_mesh):
    project = Project()
    first = project.new_item(SOURCE, box_mesh)
    project.insert_item(first)
    second = project.new_item(SOURCE, box_mesh)
    assert second.placement.position[0] > first.footprint[2]


def test_duplicate_gets_a_new_id_and_offset(box_mesh):
    project = make_project(box_mesh)
    original = project.items[0]
    copy = project.make_duplicate(original)
    assert copy.id != original.id
    assert copy.placement.position[0] == pytest.approx(original.placement.position[0] + 100.0)
    assert copy.placement.rotation_z == pytest.approx(original.placement.rotation_z)


def test_negative_scale_is_rejected(box_mesh):
    project = make_project(box_mesh)
    with pytest.raises(ValueError):
        project.set_placement(project.items[0].id, Placement(scale=-1.0))
