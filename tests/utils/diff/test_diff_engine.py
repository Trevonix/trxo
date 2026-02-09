import pytest
from trxo.utils.diff.diff_engine import DiffEngine, ChangeType


def _mock_insights(mocker):
    mocker.patch(
        "trxo.utils.diff.insights_generator.InsightsGenerator.generate_key_insights",
        return_value=[],
    )


def test_compare_data_added_item(mocker):
    engine = DiffEngine()

    current = {"result": []}
    new = {"result": [{"_id": "1", "name": "A"}]}

    mocker.patch("trxo.utils.diff.diff_engine.DeepDiff", return_value={})
    _mock_insights(mocker)

    result = engine.compare_data(current, new, "scripts", "alpha")

    assert len(result.added_items) == 1
    assert result.added_items[0].change_type == ChangeType.ADDED
    assert result.total_items_current == 0
    assert result.total_items_new == 1


def test_compare_data_removed_item(mocker):
    engine = DiffEngine()

    current = {"result": [{"_id": "1", "name": "A"}]}
    new = {"result": []}

    mocker.patch("trxo.utils.diff.diff_engine.DeepDiff", return_value={})
    _mock_insights(mocker)

    result = engine.compare_data(current, new, "scripts", "alpha")

    assert len(result.removed_items) == 1
    assert result.removed_items[0].change_type == ChangeType.REMOVED


def test_compare_data_modified_item(mocker):
    engine = DiffEngine()

    current = {"result": [{"_id": "1", "name": "A", "x": 1}]}
    new = {"result": [{"_id": "1", "name": "A", "x": 2}]}

    fake_diff = {"values_changed": {"root['x']": {"old_value": 1, "new_value": 2}}}

    diff_obj = mocker.MagicMock()
    diff_obj.to_dict.return_value = fake_diff
    diff_obj.get.side_effect = fake_diff.get
    diff_obj.__bool__.return_value = True

    mocker.patch("trxo.utils.diff.diff_engine.DeepDiff", return_value=diff_obj)
    _mock_insights(mocker)

    result = engine.compare_data(current, new, "scripts", "alpha")

    assert len(result.modified_items) == 1
    assert result.modified_items[0].change_type == ChangeType.MODIFIED
    assert result.modified_items[0].changes_count == 1


def test_compare_data_unchanged_item(mocker):
    engine = DiffEngine()

    current = {"result": [{"_id": "1", "name": "A"}]}
    new = {"result": [{"_id": "1", "name": "A"}]}

    diff_obj = mocker.MagicMock()
    diff_obj.__bool__.return_value = False

    mocker.patch("trxo.utils.diff.diff_engine.DeepDiff", return_value=diff_obj)
    _mock_insights(mocker)

    result = engine.compare_data(current, new, "scripts", "alpha")

    assert len(result.unchanged_items) == 1
    assert result.unchanged_items[0].change_type == ChangeType.UNCHANGED


def test_extract_items_from_data_wrapper():
    engine = DiffEngine()

    data = {"data": {"result": [{"_id": "1"}]}}

    items = engine._extract_items(data)

    assert items == [{"_id": "1"}]


def test_extract_items_single_object():
    engine = DiffEngine()

    data = {"_id": "1", "x": 2}

    items = engine._extract_items(data)

    assert items == [{"_id": "1", "x": 2}]


def test_create_id_map_filters_items_without_id():
    engine = DiffEngine()

    items = [{"_id": "1"}, {"x": 2}]

    id_map = engine._create_id_map(items)

    assert "1" in id_map
    assert len(id_map) == 1


def test_get_item_id_priority():
    engine = DiffEngine()

    item = {"id": "2", "_id": "1"}

    assert engine._get_item_id(item) == "1"


def test_get_item_name_priority():
    engine = DiffEngine()

    item = {"displayName": "D", "name": "N"}

    assert engine._get_item_name(item) == "N"
