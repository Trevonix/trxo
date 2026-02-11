import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from trxo.utils.hash_manager import HashManager, get_command_name_from_item_type


@pytest.fixture()
def store(tmp_path):
    store = MagicMock()
    store.base_dir = tmp_path
    return store


@pytest.fixture()
def manager(store):
    return HashManager(store)


def test_create_hash_same_data_same_hash(manager):
    data1 = {"data": {"result": [{"_id": "1", "name": "a"}]}}
    data2 = {"data": {"result": [{"_id": "1", "name": "a"}]}}

    h1 = manager.create_hash(data1, "scripts")
    h2 = manager.create_hash(data2, "scripts")

    assert h1 == h2


def test_create_hash_ignores_dynamic_fields(manager):
    data1 = {"_id": "1", "timestamp": "x"}
    data2 = {"_id": "1", "timestamp": "y"}

    h1 = manager.create_hash(data1, "scripts")
    h2 = manager.create_hash(data2, "scripts")

    assert h1 == h2


def test_save_and_get_hash_metadata(manager, store):
    manager.save_export_hash("scripts", "abc123", "/tmp/file.json")

    meta = manager.get_hash_info("scripts")

    assert meta["hash"] == "abc123"
    assert meta["file_path"] == "/tmp/file.json"
    assert meta["operation"] == "export"


def test_list_all_hashes(manager):
    manager.save_export_hash("a", "1")
    manager.save_export_hash("b", "2")

    hashes = manager.list_all_hashes()

    assert hashes["a"]["hash"] == "1"
    assert hashes["b"]["hash"] == "2"


def test_validate_import_hash_success(manager, mocker):
    mocker.patch("trxo.utils.hash_manager.success")
    mocker.patch("trxo.utils.hash_manager.error")

    data = {"_id": "1"}
    h = manager.create_hash(data, "scripts")
    manager.save_export_hash("scripts", h)

    assert manager.validate_import_hash(data, "scripts") is True


def test_validate_import_hash_mismatch(manager, mocker):
    error_mock = mocker.patch("trxo.utils.hash_manager.error")
    mocker.patch("trxo.utils.hash_manager.success")

    manager.save_export_hash("scripts", "wrong")

    result = manager.validate_import_hash({"_id": "1"}, "scripts")

    assert result is False
    assert error_mock.call_count >= 2


def test_validate_import_hash_missing_metadata(manager, mocker):
    error_mock = mocker.patch("trxo.utils.hash_manager.error")

    result = manager.validate_import_hash({"_id": "1"}, "scripts")

    assert result is False
    error_mock.assert_called_once()


def test_validate_import_hash_force_true(manager, mocker):
    mocker.patch("trxo.utils.hash_manager.warning")

    result = manager.validate_import_hash({"x": 1}, "scripts", force=True)

    assert result is True


def test_list_all_hashes_invalid_json(manager):
    file = manager.checksums_file
    file.write_text("bad json")

    assert manager.list_all_hashes() == {}


def test_get_hash_info_missing_file(manager):
    assert manager.get_hash_info("scripts") is None


def test_get_hash_info_invalid_json(manager):
    manager.checksums_file.write_text("bad")

    assert manager.get_hash_info("scripts") is None


def test_extract_items_result_array(manager):
    data = {"result": [{"_id": "1"}, {"_id": "2"}]}
    items = manager._extract_items_for_hash(data)

    assert len(items) == 2


def test_extract_items_single_object(manager):
    data = {"_id": "1"}
    items = manager._extract_items_for_hash(data)

    assert items == [data]


def test_sort_items_by_id(manager):
    items = [{"_id": "2"}, {"_id": "1"}]
    sorted_items = manager._sort_items_for_hash(items)

    assert sorted_items[0]["_id"] == "1"


def test_sort_items_by_name(manager):
    items = [{"name": "b"}, {"name": "a"}]
    sorted_items = manager._sort_items_for_hash(items)

    assert sorted_items[0]["name"] == "a"


def test_sort_items_fallback(manager):
    items = [{"x": "2"}, {"x": "1"}]
    sorted_items = manager._sort_items_for_hash(items)

    assert sorted_items[0]["x"] == "1"


def test_sort_items_uncomparable(manager):
    items = [{"x": {"a": 1}}, {"x": {"b": 2}}]
    sorted_items = manager._sort_items_for_hash(items)

    assert sorted_items == items


def test_get_command_name_from_item_type_direct():
    assert get_command_name_from_item_type("scripts") == "scripts"


def test_get_command_name_from_item_type_cleanup():
    assert get_command_name_from_item_type("policies (alpha)") == "policies"


def test_get_command_name_from_item_type_unknown():
    assert get_command_name_from_item_type("My Custom Type") == "my_custom_type"
