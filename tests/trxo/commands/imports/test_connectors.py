from unittest.mock import MagicMock
import pytest
from trxo.commands.imports.connectors import create_connectors_import_command
from trxo_lib.imports.domains.connectors import ConnectorsImporter


def test_get_required_fields():
    importer = ConnectorsImporter()
    assert importer.get_required_fields() == ["_id"]


def test_get_item_type():
    importer = ConnectorsImporter()
    assert importer.get_item_type() == "connectors"


def test_get_api_endpoint():
    importer = ConnectorsImporter()

    assert (
        importer.get_api_endpoint("provisioner.test", "http://x")
        == "http://x/openidm/config/provisioner.test"
    )


def test_update_item_missing_id():
    importer = ConnectorsImporter()

    with pytest.raises(KeyError):
        importer.update_item({}, "token", "http://x")


def test_update_item_invalid_id(mocker):
    importer = ConnectorsImporter()

    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = None

    response = MagicMock()
    response.status_code = 400
    client.put.return_value = response

    mocker.patch("httpx.Client", return_value=client)
    mocker.patch("trxo_lib.imports.domains.connectors.error")

    result = importer.update_item({"_id": "bad.id"}, "token", "http://x")

    assert result is False
    client.put.assert_called_once()


def test_update_item_success_normal_connector(mocker):
    importer = ConnectorsImporter()

    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = None

    response = MagicMock()
    response.status_code = 200
    client.put.return_value = response

    mocker.patch("httpx.Client", return_value=client)
    mocker.patch("trxo_lib.imports.domains.connectors.success")

    data = {
        "_id": "provisioner.openicf/mysql",
        "connectorRef": {"displayName": "MySQL"},
    }

    result = importer.update_item(data, "token", "http://x")

    assert result is True
    client.put.assert_called_once()


def test_update_item_error(mocker):
    importer = ConnectorsImporter()

    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = None

    client.put.side_effect = Exception("boom")

    mocker.patch("httpx.Client", return_value=client)
    mocker.patch("trxo_lib.imports.domains.connectors.error")

    data = {"_id": "provisioner.openicf.mysql"}

    result = importer.update_item(data, "token", "http://x")

    assert result is False


def test_create_connectors_import_command_wires_service(mocker):
    mock_service = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.connectors.ImportService", return_value=mock_service
    )

    cmd = create_connectors_import_command()
    cmd(file="f.json")

    mock_service.import_connectors.assert_called_once()
