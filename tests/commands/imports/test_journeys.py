import pytest
import typer

from trxo.commands.imports.journeys import (
    JourneyImporter,
    create_journey_import_command,
)


def test_journey_required_fields():
    importer = JourneyImporter()
    assert importer.get_required_fields() == ["_id"]


def test_journey_item_type():
    importer = JourneyImporter()
    assert importer.get_item_type() == "journeys"


def test_journey_api_endpoint():
    importer = JourneyImporter(realm="alpha")
    url = importer.get_api_endpoint("j1", "http://x")
    assert url.endswith("/am/json/realms/root/realms/alpha/realm-config/authentication/authenticationtrees/trees/j1")


def test_journey_update_success(mocker):
    importer = JourneyImporter()
    importer.make_http_request = mocker.Mock()
    mocker.patch("trxo.commands.imports.journeys.info")

    data = {"_id": "j1", "_rev": "1", "name": "test"}

    assert importer.update_item(data, "t", "http://x") is True
    importer.make_http_request.assert_called_once()


def test_journey_update_missing_id(mocker):
    importer = JourneyImporter()
    mocker.patch("trxo.commands.imports.journeys.error")

    assert importer.update_item({}, "t", "http://x") is False


def test_journey_update_failure(mocker):
    importer = JourneyImporter()
    importer.make_http_request = mocker.Mock(side_effect=Exception("boom"))
    mocker.patch("trxo.commands.imports.journeys.error")

    data = {"_id": "j1"}

    assert importer.update_item(data, "t", "http://x") is False


def test_create_journey_import_command_calls_import(mocker):
    importer = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.journeys.JourneyImporter",
        return_value=importer,
    )

    cmd = create_journey_import_command()
    cmd(file="f.json", realm="alpha", cherry_pick="a,b")

    importer.import_from_file.assert_called_once()


def test_create_journey_import_command_defaults(mocker):
    importer = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.journeys.JourneyImporter",
        return_value=importer,
    )

    cmd = create_journey_import_command()
    cmd()

    importer.import_from_file.assert_called_once()
