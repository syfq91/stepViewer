import pytest
from PySide6.QtGui import QUndoStack

from stepviewer.core.commands import (
    AddItemCommand,
    DeleteItemsCommand,
    DuplicateItemsCommand,
    SetFieldCommand,
    TransformItemCommand,
)
from stepviewer.core.project import Project
from stepviewer.core.transform import Placement

SOURCE = "/models/table.step"


@pytest.fixture
def project(qapp, box_mesh) -> Project:
    project = Project()
    item = project.new_item(SOURCE, box_mesh, placement=Placement((0.0, 0.0, 0.0)))
    project.insert_item(item)
    return project


@pytest.fixture
def stack(qapp) -> QUndoStack:
    return QUndoStack()


def test_add_command_is_undoable(project, stack, box_mesh):
    new_item = project.new_item(SOURCE, box_mesh, name="Sofa")
    stack.push(AddItemCommand(project, new_item))
    assert len(project) == 2
    assert project.get(new_item.id) is not None

    stack.undo()
    assert len(project) == 1
    assert project.get(new_item.id) is None

    stack.redo()
    assert len(project) == 2


def test_transform_command_restores_the_previous_placement(project, stack):
    item = project.items[0]
    before = item.placement
    after = Placement((1200.0, 400.0, 0.0), 45.0, 1.0)

    stack.push(TransformItemCommand(project, item.id, before, after))
    assert project.get(item.id).placement == after

    stack.undo()
    assert project.get(item.id).placement == before

    stack.redo()
    assert project.get(item.id).placement == after


def test_delete_command_restores_items_at_their_original_index(project, stack, box_mesh):
    second = project.new_item(SOURCE, box_mesh, name="Second")
    project.insert_item(second)

    stack.push(DeleteItemsCommand(project, [project.items[0].id]))
    assert [item.name for item in project.items] == ["Second"]

    stack.undo()
    assert len(project) == 2
    assert project.items[0].id != second.id


def test_set_field_command(project, stack):
    item = project.items[0]
    stack.push(SetFieldCommand(project, item.id, "locked", False, True))
    assert project.get(item.id).locked is True
    stack.undo()
    assert project.get(item.id).locked is False


def test_duplicate_command_is_undoable(project, stack):
    original = project.items[0]
    stack.push(DuplicateItemsCommand(project, [original.id]))
    assert len(project) == 2
    copy = project.items[1]
    assert copy.id != original.id

    stack.undo()
    assert len(project) == 1
    assert project.get(copy.id) is None


def test_undo_stack_labels(project, stack):
    item = project.items[0]
    stack.push(TransformItemCommand(project, item.id, item.placement, item.placement))
    assert "Move" in stack.undoText()
