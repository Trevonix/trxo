import json

import pytest
from trxo_lib.imports.processor import TrxoAbort

from trxo.commands.imports.oauth import create_oauth_import_command
from trxo_lib.imports.domains.oauth import OAuthImporter
from trxo_lib.config.constants import DEFAULT_REALM


def test_parse_oauth_data_standard_format(mocker):
    importer = OAuthImporter(realm=DEFAULT_REALM)

    data = {
        "data": {
            "clients": [{"_id": "c1"}],
            "scripts": [{"_id": "s1"}],
        }
    }

    clients = importer._parse_oauth_data(data)

    assert clients == [{"_id": "c1"}]
    assert importer._pending_scripts == [{"_id": "s1"}]


def test_parse_oauth_data_legacy_format(mocker):
    importer = OAuthImporter(realm=DEFAULT_REALM)

    data = {
        "clients": [{"_id": "c1"}],
        "scripts": [{"_id": "s1"}],
    }

    clients = importer._parse_oauth_data(data)

    assert clients == [{"_id": "c1"}]
    assert importer._pending_scripts == [{"_id": "s1"}]


def test_parse_oauth_data_list_format(mocker):
    importer = OAuthImporter(realm=DEFAULT_REALM)

    data = [{"_id": "c1"}]

    clients = importer._parse_oauth_data(data)

    assert clients == [{"_id": "c1"}]


def test_import_from_local_happy_path(mocker, tmp_path):
    importer = OAuthImporter(realm=DEFAULT_REALM)

    data = {
        "data": {
            "clients": [{"_id": "c1"}],
            "scripts": [],
        }
    }

    file_path = tmp_path / "oauth.json"
    file_path.write_text(json.dumps(data))

    mocker.patch.object(importer, "validate_import_hash", return_value=True)
    mocker.patch.object(importer, "_validate_items")

    result = importer._import_from_local(str(file_path), force_import=False)

    assert result == [{"_id": "c1"}]


def test_import_from_local_file_not_found_raises_abort(mocker):
    importer = OAuthImporter(realm=DEFAULT_REALM)

    with pytest.raises(TrxoAbort):
        importer._import_from_local("missing.json", force_import=False)


def test_process_items_calls_script_importer_first(mocker):
    importer = OAuthImporter(realm=DEFAULT_REALM)

    importer._pending_scripts = [{"_id": "s1"}]

    mocker.patch.object(importer.script_importer, "update_item", return_value=True)

    mocker.patch(
        "trxo_lib.imports.domains.oauth.BaseImporter.process_items",
        return_value=None,
    )

    importer.process_items(
        items=[{"_id": "c1"}],
        token="token",
        base_url="https://base",
    )

    assert importer.script_importer is not None


def test_update_item_happy_path(mocker):
    importer = OAuthImporter(realm=DEFAULT_REALM)

    mock_response = mocker.Mock()
    mock_response.status_code = 200

    mocker.patch.object(importer, "make_http_request", return_value=mock_response)
    mocker.patch.object(importer, "build_auth_headers", return_value={})

    result = importer.update_item({"_id": "c1", "name": "x"}, "token", "https://base")

    assert result is True


def test_update_item_missing_id_returns_false(mocker):
    importer = OAuthImporter(realm=DEFAULT_REALM)

    mocker.patch("trxo_lib.imports.domains.oauth.error")

    result = importer.update_item({}, "token", "https://base")

    assert result is False


def test_delete_item_happy_path(mocker):
    importer = OAuthImporter(realm=DEFAULT_REALM)

    mock_response = mocker.Mock()
    mock_response.status_code = 200

    mocker.patch.object(importer, "make_http_request", return_value=mock_response)
    mocker.patch.object(importer, "build_auth_headers", return_value={})

    result = importer.delete_item("c1", "token", "https://base")

    assert result is True


def test_delete_item_failure_returns_false(mocker):
    importer = OAuthImporter(realm=DEFAULT_REALM)

    mocker.patch.object(importer, "make_http_request", side_effect=Exception("fail"))
    mocker.patch.object(importer, "build_auth_headers", return_value={})
    mocker.patch("trxo_lib.imports.domains.oauth.error")

    result = importer.delete_item("c1", "token", "https://base")

    assert result is False


def test_create_oauth_import_command_calls_service(mocker):
    mock_service = mocker.Mock()
    mocker.patch("trxo.commands.imports.oauth.ImportService", return_value=mock_service)

    cmd = create_oauth_import_command()
    cmd(file="data.json")

    mock_service.import_oauth.assert_called_once()
