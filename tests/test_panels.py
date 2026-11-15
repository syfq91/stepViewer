"""Panel behaviour that does not need the VTK viewport."""

import pytest
from PySide6.QtCore import Qt

from stepviewer.core.item import SceneItem
from stepviewer.core.transform import Placement
from stepviewer.ui.properties_panel import PropertiesPanel
from stepviewer.ui.scene_panel import ScenePanel


@pytest.fixture
def item(box_mesh) -> SceneItem:
    return SceneItem(
        id="item-1",
        name="Table",
        source_path="/models/table.step",
        mesh=box_mesh,
        placement=Placement((100.0, 200.0, 0.0), 0.0, 1.0),
    )


# ------------------------------------------------------------------ properties
def test_properties_show_the_selected_item(qapp, item):
    panel = PropertiesPanel()
    panel.set_item(item)

    assert panel.name.text() == "Table"
    assert panel.x.value() == pytest.approx(100.0)
    assert panel.y.value() == pytest.approx(200.0)
    assert panel.scale.value() == pytest.approx(1.0)
    assert panel.x.isEnabled()


def test_properties_are_disabled_without_a_selection(qapp):
    panel = PropertiesPanel()
    panel.set_item(None)
    assert not panel.x.isEnabled()
    assert not panel.locked.isEnabled()


def test_show_placement_updates_fields_without_emitting(qapp, item):
    panel = PropertiesPanel()
    panel.set_item(item)

    seen = []
    panel.placement_edited.connect(lambda *args: seen.append(args))
    panel.show_placement(Placement((500.0, 600.0, 50.0), 30.0, 2.0))

    assert panel.x.value() == pytest.approx(500.0)
    assert panel.z.value() == pytest.approx(50.0)
    assert panel.rotation.value() == pytest.approx(30.0)
    assert panel.scale.value() == pytest.approx(2.0)
    assert seen == []


def test_editing_a_field_emits_a_placement(qapp, item):
    panel = PropertiesPanel()
    panel.set_item(item)

    seen = []
    panel.placement_edited.connect(lambda item_id, placement: seen.append((item_id, placement)))

    panel.x.setValue(750.0)
    panel.x.editingFinished.emit()

    assert len(seen) == 1
    item_id, placement = seen[0]
    assert item_id == item.id
    assert placement.position == pytest.approx((750.0, 200.0, 0.0))


def test_unchanged_placement_is_not_emitted(qapp, item):
    panel = PropertiesPanel()
    panel.set_item(item)

    seen = []
    panel.placement_edited.connect(lambda *args: seen.append(args))
    panel.x.editingFinished.emit()
    assert seen == []


def test_lock_checkbox_emits_a_field_change(qapp, item):
    panel = PropertiesPanel()
    panel.set_item(item)

    seen = []
    panel.field_edited.connect(lambda *args: seen.append(args))
    panel.locked.setChecked(True)
    assert seen == [(item.id, "locked", True)]


# ------------------------------------------------------------------ scene panel
def test_scene_panel_lists_items_with_source_names(qapp, item):
    panel = ScenePanel()
    panel.set_items([item])

    assert panel.tree.topLevelItemCount() == 1
    node = panel.tree.topLevelItem(0)
    assert node.text(0) == "Table"
    assert node.text(1) == "table.step"
    assert node.checkState(0) == Qt.Checked


def test_sync_updates_in_place_without_telling_the_application(qapp, item):
    panel = ScenePanel()
    panel.set_items([item])

    emitted = []
    panel.rename_requested.connect(lambda *args: emitted.append(args))
    panel.visibility_toggled.connect(lambda *args: emitted.append(args))

    item.name = "Dining table"
    item.visible = False
    panel.sync([item])

    node = panel.tree.topLevelItem(0)
    assert node.text(0) == "Dining table"
    assert node.checkState(0) == Qt.Unchecked
    assert emitted == []


def test_selection_is_reflected_in_the_tree(qapp, item):
    panel = ScenePanel()
    panel.set_items([item])
    panel.set_selection([item.id])

    selected = panel.tree.selectedItems()
    assert len(selected) == 1
    assert selected[0].data(0, Qt.UserRole) == item.id


def test_user_rename_and_visibility_are_reported(qapp, item):
    panel = ScenePanel()
    panel.set_items([item])

    renames, visibilities = [], []
    panel.rename_requested.connect(lambda *args: renames.append(args))
    panel.visibility_toggled.connect(lambda *args: visibilities.append(args))

    panel.tree.topLevelItem(0).setText(0, "Chair")
    panel.tree.topLevelItem(0).setCheckState(0, Qt.Unchecked)

    assert renames == [(item.id, "Chair")]
    assert visibilities == [(item.id, False)]
