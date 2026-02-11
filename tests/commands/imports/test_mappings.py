import json
import tempfile
import os

from trxo.commands.imports.mappings import (
    MappingsImporter,
    create_mappings_import_command,
)


def test_mappings_required_fields():
    importer = MappingsImporter()
    assert importer.get_required_fields() == ["name"]


def test_mappings_item_type():
    importer = MappingsImporter()
    assert importer.get_item_type() == "sync mappings"


def test_mappings_api_endpoint():
    importer = MappingsImporter()
    assert importer.get_api_endpoint("", "http://x") == "http://x/openidm/config/sync"


def test_find_mapping_by_name_found():
    importer = MappingsImporter()
    idx, mapping = importer._find_mapping_by_name(
        [{"name": "a"}, {"name": "b"}], "b"
    )
    assert idx == 1
    assert mapping["name"] == "b"


def test_find_mapping_by_name_not_found():
    importer = MappingsImporter()
    idx, mapping = importer._find_mapping_by_name([{"name": "a"}], "x")
    assert idx == -1
    assert mapping is None


def test_generate_patch_operations_replace():
    importer = MappingsImporter()
    ops = importer._generate_patch_operations(
        {"name": "a", "x": 1},
        {"name": "a", "x": 2},
    )
    assert ops[0]["operation"] == "replace"


def test_generate_patch_operations_list_replace():
    importer = MappingsImporter()
    ops = importer._generate_patch_operations(
        {"policies": [1]},
        {"policies": [2]},
    )
    assert ops[0]["operation"] == "replace"


def test_update_item_missing_name(mocker):
    importer = MappingsImporter()
    mocker.patch("trxo.commands.imports.mappings.error")

    assert importer.update_item({}, "t", "http://x") is False


def test_update_item_no_current_config(mocker):
    importer = MappingsImporter()
    importer._get_current_sync_config = mocker.Mock(return_value={})
    mocker.patch("trxo.commands.imports.mappings.error")

    assert importer.update_item({"name": "a"}, "t", "http://x") is False


def test_update_item_existing_no_changes(mocker):
    importer = MappingsImporter()
    importer.make_http_request = mocker.Mock()
    importer._get_current_sync_config = mocker.Mock(
        return_value={"mappings": [{"name": "a"}]}
    )
    mocker.patch("trxo.commands.imports.mappings.info")

    assert importer.update_item({"name": "a"}, "t", "http://x") is True


def test_update_item_existing_with_patch(mocker):
    importer = MappingsImporter()
    importer.make_http_request = mocker.Mock()
    importer._get_current_sync_config = mocker.Mock(
        return_value={"mappings": [{"name": "a", "x": 1}]}
    )
    mocker.patch("trxo.commands.imports.mappings.info")

    assert importer.update_item({"name": "a", "x": 2}, "t", "http://x") is True


def test_update_item_create_new(mocker):
    importer = MappingsImporter()
    importer.make_http_request = mocker.Mock()
    importer._get_current_sync_config = mocker.Mock(
        return_value={"mappings": []}
    )
    mocker.patch("trxo.commands.imports.mappings.info")

    assert importer.update_item({"name": "a"}, "t", "http://x") is True


def test_load_mappings_file_raw_list():
    importer = MappingsImporter()

    with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as f:
        json.dump([{"name": "a"}], f)
        path = f.name

    data = importer._load_mappings_file(path)
    os.unlink(path)

    assert data[0]["name"] == "a"


def test_load_mappings_file_raw_object():
    importer = MappingsImporter()

    with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as f:
        json.dump({"name": "a"}, f)
        path = f.name

    data = importer._load_mappings_file(path)
    os.unlink(path)

    assert data["name"] == "a"


def test_create_mappings_import_command(mocker):
    importer = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.mappings.MappingsImporter",
        return_value=importer,
    )

    cmd = create_mappings_import_command()
    cmd(file="x.json")

    importer.import_from_file.assert_called_once()
