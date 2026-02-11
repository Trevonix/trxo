import json
import pytest
from trxo.commands.imports.managed import ManagedObjectsImporter, create_managed_import_command


def test_find_object_by_name_found():
    imp = ManagedObjectsImporter()
    objs = [{"name": "a"}, {"name": "b"}]
    idx, obj = imp._find_object_by_name(objs, "b")
    assert idx == 1
    assert obj["name"] == "b"


def test_find_object_by_name_not_found():
    imp = ManagedObjectsImporter()
    idx, obj = imp._find_object_by_name([{"name": "a"}], "x")
    assert idx == -1
    assert obj is None


def test_generate_patch_operations_replace_and_add():
    imp = ManagedObjectsImporter()
    existing = {"a": 1}
    new = {"a": 2, "b": 3}
    ops = imp._generate_patch_operations(existing, new, "/objects/0")
    assert {"operation": "replace", "field": "/objects/0/a", "value": 2} in ops
    assert {"operation": "add", "field": "/objects/0/b", "value": 3} in ops


def test_generate_patch_operations_nested():
    imp = ManagedObjectsImporter()
    existing = {"a": {"x": 1}}
    new = {"a": {"x": 2}}
    ops = imp._generate_patch_operations(existing, new, "/objects/0")
    assert {"operation": "replace", "field": "/objects/0/a/x", "value": 2} in ops


def test_get_current_managed_config_success(mocker):
    imp = ManagedObjectsImporter()
    resp = mocker.Mock()
    resp.json.return_value = {"objects": []}
    imp.make_http_request = mocker.Mock(return_value=resp)
    out = imp._get_current_managed_config("t", "http://x")
    assert out == {"objects": []}


def test_get_current_managed_config_error(mocker):
    imp = ManagedObjectsImporter()
    imp.make_http_request = mocker.Mock(side_effect=Exception("boom"))
    mocker.patch("trxo.commands.imports.managed.error")
    out = imp._get_current_managed_config("t", "http://x")
    assert out == {}


def test_update_item_single_create_success(mocker):
    imp = ManagedObjectsImporter()
    mocker.patch("trxo.commands.imports.managed.info")
    imp._get_current_managed_config = mocker.Mock(return_value={"objects": []})
    imp.make_http_request = mocker.Mock()
    imp._update_relationship_properties = mocker.Mock()
    imp._delete_orphaned_properties = mocker.Mock()

    data = {"name": "obj1"}
    assert imp.update_item(data, "t", "http://x") is True


def test_update_item_single_update_with_patch(mocker):
    imp = ManagedObjectsImporter()
    mocker.patch("trxo.commands.imports.managed.info")
    imp._get_current_managed_config = mocker.Mock(return_value={"objects": [{"name": "obj1", "x": 1}]})
    imp.make_http_request = mocker.Mock()
    imp._update_relationship_properties = mocker.Mock()
    imp._delete_orphaned_properties = mocker.Mock()

    data = {"name": "obj1", "x": 2}
    assert imp.update_item(data, "t", "http://x") is True


def test_update_item_single_no_changes(mocker):
    imp = ManagedObjectsImporter()
    mocker.patch("trxo.commands.imports.managed.info")
    imp._get_current_managed_config = mocker.Mock(return_value={"objects": [{"name": "obj1"}]})
    imp.make_http_request = mocker.Mock()
    imp._delete_orphaned_properties = mocker.Mock()

    data = {"name": "obj1"}
    assert imp.update_item(data, "t", "http://x") is True


def test_update_item_single_missing_name(mocker):
    imp = ManagedObjectsImporter()
    mocker.patch("trxo.commands.imports.managed.error")
    assert imp.update_item({}, "t", "http://x") is False


def test_update_item_multi_objects_patch_and_put(mocker):
    imp = ManagedObjectsImporter()
    mocker.patch("trxo.commands.imports.managed.info")
    imp._get_current_managed_config = mocker.Mock(
        return_value={"objects": [{"name": "a"}]}
    )
    imp.make_http_request = mocker.Mock()
    imp._update_relationship_properties = mocker.Mock()
    imp._delete_orphaned_properties = mocker.Mock()

    data = {
        "objects": [
            {"name": "a", "x": 2},
            {"name": "b"},
        ]
    }

    assert imp.update_item(data, "t", "http://x") is True


def test_update_item_multi_objects_skip_invalid_entries(mocker):
    imp = ManagedObjectsImporter()
    mocker.patch("trxo.commands.imports.managed.warning")
    imp._get_current_managed_config = mocker.Mock(return_value={"objects": []})
    imp.make_http_request = mocker.Mock()

    data = {"objects": [123, {"no": "name"}]}
    assert imp.update_item(data, "t", "http://x") is True


def test_update_item_multi_get_current_config_fail(mocker):
    imp = ManagedObjectsImporter()
    mocker.patch("trxo.commands.imports.managed.error")
    imp._get_current_managed_config = mocker.Mock(return_value={})

    data = {"objects": [{"name": "a"}]}
    assert imp.update_item(data, "t", "http://x") is False


def test_load_managed_objects_file_raw_dict(tmp_path):
    f = tmp_path / "m.json"
    f.write_text(json.dumps({"name": "a"}))
    imp = ManagedObjectsImporter()
    out = imp._load_managed_objects_file(str(f))
    assert out["name"] == "a"


def test_load_managed_objects_file_export_result(tmp_path):
    f = tmp_path / "m.json"
    f.write_text(json.dumps({"data": {"result": [{"name": "a"}]}}))
    imp = ManagedObjectsImporter()
    out = imp._load_managed_objects_file(str(f))
    assert out[0]["name"] == "a"


def test_load_data_from_file_objects_array(tmp_path, mocker):
    f = tmp_path / "m.json"
    f.write_text(json.dumps({"objects": [{"name": "a"}]}))
    imp = ManagedObjectsImporter()
    out = imp.load_data_from_file(str(f))
    assert out[0]["name"] == "a"


def test_load_data_from_file_list(tmp_path):
    f = tmp_path / "m.json"
    f.write_text(json.dumps([{"name": "a"}]))
    imp = ManagedObjectsImporter()
    out = imp.load_data_from_file(str(f))
    assert out[0]["name"] == "a"


def test_load_data_from_file_invalid(tmp_path):
    f = tmp_path / "m.json"
    f.write_text(json.dumps("bad"))
    imp = ManagedObjectsImporter()
    with pytest.raises(ValueError):
        imp.load_data_from_file(str(f))


def test_create_managed_import_command_wires_importer(mocker, tmp_path):
    f = tmp_path / "m.json"
    f.write_text(json.dumps({"data": []}))

    importer = mocker.Mock()
    mocker.patch("trxo.commands.imports.managed.ManagedObjectsImporter", return_value=importer)

    cmd = create_managed_import_command()
    cmd(file=str(f))

    importer.import_from_file.assert_called_once()
