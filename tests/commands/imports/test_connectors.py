import json
import pytest
import typer

from trxo.commands.imports.connectors import (
    ConnectorsImporter,
    create_connectors_import_command,
)


def test_get_required_fields():
    importer = ConnectorsImporter()
    assert importer.get_required_fields() == ["_id"]


def test_get_item_type():
    importer = ConnectorsImporter()
    assert importer.get_item_type() == "IDM connectors"


def test_get_api_endpoint():
    importer = ConnectorsImporter()
    assert (
        importer.get_api_endpoint("provisioner.test", "http://x")
        == "http://x/openidm/config/provisioner.test"
    )


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


def test_update_item_error(mocker):
    importer = ConnectorsImporter()
    importer.make_http_request = mocker.Mock(side_effect=Exception("boom"))

    mocker.patch("trxo.commands.imports.connectors.error")

    data = {"_id": "provisioner.openicf.mysql"}

    result = importer.update_item(data, "t", "http://x")
    assert result is False
    importer.make_http_request.assert_called_once()


def test_create_connectors_import_command_wires_options(mocker):
    importer = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.connectors.ConnectorsImporter", return_value=importer
    )

    cmd = create_connectors_import_command()
    cmd(file="f.json")

    importer.import_from_file.assert_called_once()
