import json
import pytest
from trxo.commands.imports.webhooks import create_webhooks_import_command
from trxo_lib.imports.domains.webhooks import WebhooksImporter


def test_get_required_fields():
    importer = WebhooksImporter(realm="alpha")
    assert importer.get_required_fields() == ["_id"]


def test_get_item_type():
    importer = WebhooksImporter(realm="alpha")
    assert importer.get_item_type() == "webhooks"


def test_get_api_endpoint():
    importer = WebhooksImporter(realm="alpha")
    url = importer.get_api_endpoint("w1", "http://x")
    assert url.endswith("/am/json/realms/root/realms/alpha/realm-config/webhooks/w1")


def test_update_item_success_strips_rev(mocker):
    importer = WebhooksImporter(realm="alpha")

    importer.make_http_request = mocker.Mock()
    mocker.patch("trxo_lib.imports.domains.webhooks.info")

    data = {"_id": "w1", "_rev": "123", "name": "hook"}

    result = importer.update_item(data, "t", "http://x")

    assert result is True

    args = importer.make_http_request.call_args.args
    payload = json.loads(args[3])

    assert payload["_id"] == "w1"
    assert "_rev" not in payload


def test_update_item_missing_id(mocker):
    importer = WebhooksImporter(realm="alpha")

    mocker.patch("trxo_lib.imports.domains.webhooks.error")

    result = importer.update_item({}, "t", "http://x")

    assert result is False


def test_update_item_exception(mocker):
    importer = WebhooksImporter(realm="alpha")

    importer.make_http_request = mocker.Mock(side_effect=Exception("boom"))
    mocker.patch("trxo_lib.imports.domains.webhooks.error")

    data = {"_id": "w1"}

    result = importer.update_item(data, "t", "http://x")

    assert result is False


def test_create_webhooks_import_command_wires_service(mocker):
    mock_service = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.webhooks.ImportService", return_value=mock_service
    )

    cmd = create_webhooks_import_command()
    cmd(file="f.json", realm="alpha")

    mock_service.import_webhooks.assert_called_once()
    assert mock_service.import_webhooks.call_args.kwargs["realm"] == "alpha"
