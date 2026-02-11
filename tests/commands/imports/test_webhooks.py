import json
import pytest

from trxo.commands.imports.webhooks import (
    WebhooksImporter,
    create_webhooks_import_command,
)


def test_get_required_fields():
    importer = WebhooksImporter(realm="alpha")
    assert importer.get_required_fields() == ["_id"]


def test_get_item_type():
    importer = WebhooksImporter(realm="alpha")
    assert importer.get_item_type() == "webhooks (alpha)"


def test_get_api_endpoint():
    importer = WebhooksImporter(realm="alpha")
    url = importer.get_api_endpoint("w1", "http://x")
    assert url.endswith(
        "/am/json/realms/root/realms/alpha/realm-config/webhooks/w1"
    )


def test_update_item_success_strips_rev(mocker):
    importer = WebhooksImporter(realm="alpha")

    importer.make_http_request = mocker.Mock()
    mocker.patch("trxo.commands.imports.webhooks.info")

    data = {"_id": "w1", "_rev": "123", "name": "hook"}

    result = importer.update_item(data, "t", "http://x")

    assert result is True

    args = importer.make_http_request.call_args.args
    payload = json.loads(args[3])

    assert payload["_id"] == "w1"
    assert " _rev" not in payload
    assert "_rev" not in payload


def test_update_item_missing_id(mocker):
    importer = WebhooksImporter(realm="alpha")

    mocker.patch("trxo.commands.imports.webhooks.error")

    result = importer.update_item({}, "t", "http://x")

    assert result is False


def test_update_item_exception(mocker):
    importer = WebhooksImporter(realm="alpha")

    importer.make_http_request = mocker.Mock(side_effect=Exception("boom"))
    mocker.patch("trxo.commands.imports.webhooks.error")

    data = {"_id": "w1"}

    result = importer.update_item(data, "t", "http://x")

    assert result is False


def test_create_webhooks_import_command_wires_importer(mocker, tmp_path):
    f = tmp_path / "webhooks.json"
    f.write_text(json.dumps({"data": []}))

    importer = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.webhooks.WebhooksImporter",
        return_value=importer,
    )

    cmd = create_webhooks_import_command()
    cmd(file=str(f), realm="alpha")

    importer.import_from_file.assert_called_once()
