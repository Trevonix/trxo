import json
import pytest
import typer

from trxo.commands.imports.connectors import ConnectorsImporter, create_connectors_import_command


def test_get_required_fields():
    importer = ConnectorsImporter()
    assert importer.get_required_fields() == ["_id"]


def test_get_item_type():
    importer = ConnectorsImporter()
    assert importer.get_item_type() == "IDM connectors"


def test_get_api_endpoint():
    importer = ConnectorsImporter()
    assert importer.get_api_endpoint("provisioner.test", "http://x") == "http://x/openidm/config/provisioner.test"


def test_update_item_missing_id(mocker):
    importer = ConnectorsImporter()
    result = importer.update_item({}, "t", "u")
    assert result is False


def test_update_item_invalid_id(mocker):
    importer = ConnectorsImporter()
    result = importer.update_item({"_id": "bad.id"}, "t", "u")
    assert result is False


def test_update_item_success_normal_connector(mocker):
    importer = ConnectorsImporter()
    importer.make_http_request = mocker.Mock()

    data = {
        "_id": "provisioner.openicf/mysql",
        "connectorRef": {"displayName": "MySQL"},
    }

    result = importer.update_item(data, "t", "http://x")
    assert result is True
    importer.make_http_request.assert_called_once()


def test_update_item_success_info_provider_with_delay(mocker):
    importer = ConnectorsImporter()
    importer.make_http_request = mocker.Mock()
    mocker.patch("time.sleep")

    data = {"_id": "provisioner.openicf.connectorinfoprovider"}

    result = importer.update_item(data, "t", "http://x")
    assert result is True
    importer.make_http_request.assert_called_once()


def test_update_item_metadata_retry_then_success(mocker):
    importer = ConnectorsImporter()
    importer.max_retries = 2

    err = Exception("metadata provider not ready")
    importer.make_http_request = mocker.Mock(side_effect=[err, None])

    mocker.patch("trxo.commands.imports.connectors.info")
    mocker.patch("time.sleep")

    data = {"_id": "provisioner.openicf.connectorinfoprovider"}

    result = importer.update_item(data, "t", "http://x")
    assert result is True
    assert importer.make_http_request.call_count == 2


def test_update_item_metadata_retry_exhausted(mocker):
    importer = ConnectorsImporter()
    importer.max_retries = 2

    importer.make_http_request = mocker.Mock(
        side_effect=Exception("metadata provider not ready")
    )

    mocker.patch("trxo.commands.imports.connectors.info")
    mocker.patch("time.sleep")

    data = {"_id": "provisioner.openicf.connectorinfoprovider"}

    result = importer.update_item(data, "t", "http://x")
    assert result is False
    assert importer.make_http_request.call_count == 2


def test_update_item_non_metadata_error(mocker):
    importer = ConnectorsImporter()
    importer.make_http_request = mocker.Mock(side_effect=Exception("boom"))

    mocker.patch("trxo.commands.imports.connectors.info")

    data = {"_id": "provisioner.openicf.mysql"}

    result = importer.update_item(data, "t", "http://x")
    assert result is False
    importer.make_http_request.assert_called_once()


def test_load_connectors_file_array(tmp_path):
    f = tmp_path / "c.json"
    f.write_text(json.dumps([{"_id": "provisioner.x"}]))

    importer = ConnectorsImporter()
    data = importer._load_connectors_file(str(f))

    assert isinstance(data, list)
    assert data[0]["_id"] == "provisioner.x"


def test_load_connectors_file_single_object(tmp_path):
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"_id": "provisioner.x"}))

    importer = ConnectorsImporter()
    data = importer._load_connectors_file(str(f))

    assert isinstance(data, list)
    assert data[0]["_id"] == "provisioner.x"


def test_load_connectors_file_export_format(tmp_path):
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"data": {"result": [{"_id": "provisioner.x"}]}}))

    importer = ConnectorsImporter()
    data = importer._load_connectors_file(str(f))

    assert isinstance(data, list)
    assert data[0]["_id"] == "provisioner.x"


def test_load_connectors_file_not_found():
    importer = ConnectorsImporter()
    with pytest.raises(FileNotFoundError):
        importer._load_connectors_file("nope.json")


def test_import_from_file_git_mode_delegates_to_base(mocker):
    importer = ConnectorsImporter()
    mocker.patch.object(importer, "_get_storage_mode", return_value="git")
    mocker.patch("trxo.commands.imports.connectors.BaseImporter.import_from_file")

    importer.import_from_file(file_path=None)

    from trxo.commands.imports.connectors import BaseImporter
    BaseImporter.import_from_file.assert_called_once()


def test_import_from_file_local_success_array(mocker):
    importer = ConnectorsImporter()
    mocker.patch.object(importer, "_get_storage_mode", return_value="local")
    mocker.patch.object(importer, "initialize_auth", return_value=("t", "http://x"))
    mocker.patch.object(importer, "_load_connectors_file", return_value=[
        {"_id": "provisioner.openicf.connectorinfoprovider"},
        {"_id": "provisioner.openicf.mysql"},
    ])
    mocker.patch.object(importer, "update_item", return_value=True)
    mocker.patch("time.sleep")

    importer.import_from_file(file_path="x.json")


def test_import_from_file_local_invalid_connector_format(mocker):
    importer = ConnectorsImporter()
    mocker.patch.object(importer, "_get_storage_mode", return_value="local")
    mocker.patch.object(importer, "initialize_auth", return_value=("t", "u"))
    mocker.patch.object(importer, "_load_connectors_file", return_value={"bad": 1})

    importer.import_from_file(file_path="x.json")


def test_import_from_file_local_no_valid_connectors(mocker):
    importer = ConnectorsImporter()
    mocker.patch.object(importer, "_get_storage_mode", return_value="local")
    mocker.patch.object(importer, "initialize_auth", return_value=("t", "u"))
    mocker.patch.object(importer, "_load_connectors_file", return_value=[{"_id": "bad.id"}])

    importer.import_from_file(file_path="x.json")


def test_create_connectors_import_command_wires_options(mocker):
    importer = mocker.Mock()
    mocker.patch("trxo.commands.imports.connectors.ConnectorsImporter", return_value=importer)

    cmd = create_connectors_import_command()
    cmd(file="f.json", max_retries=9, skip_delays=True, wait_time=2)

    importer.import_from_file.assert_called_once()
    assert importer.max_retries == 9
    assert importer.skip_delays is True
    assert importer.wait_time == 2
