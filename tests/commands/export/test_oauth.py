import base64
import pytest
from trxo.commands.export.oauth import create_oauth_export_command, OAuthExporter
from trxo.constants import DEFAULT_REALM, IGNORED_SCRIPT_IDS


def test_extract_script_ids_nested():
    exporter = OAuthExporter()

    data = {
        "tokenScript": "script1",
        "nested": {
            "preAuthScript": "script2",
            "list": [
                {"postAuthScript": "script3"},
                {"nope": "x"},
            ],
        },
        "emptyScript": "[Empty]",
    }

    script_ids = exporter.extract_script_ids(data)

    assert script_ids == {"script1", "script2", "script3"}


def test_fetch_oauth_client_data_success(mocker):
    exporter = OAuthExporter()
    response = mocker.Mock()
    response.json.return_value = {"_id": "client1", "name": "test", "_rev": "123"}

    mocker.patch.object(exporter, "make_http_request", return_value=response)
    mocker.patch.object(exporter, "build_auth_headers", return_value={})

    data = exporter.fetch_oauth_client_data("client1", "token", "https://base")

    assert data["_id"] == "client1"
    assert "_rev" not in data


def test_fetch_oauth_client_data_error_returns_empty(mocker):
    exporter = OAuthExporter()
    mocker.patch.object(exporter, "make_http_request", side_effect=Exception("boom"))

    data = exporter.fetch_oauth_client_data("client1", "token", "https://base")

    assert data == {}


def test_fetch_script_data_decodes_base64(mocker):
    exporter = OAuthExporter()
    raw_script = "print('hi')"
    encoded = base64.b64encode(raw_script.encode()).decode()

    response = mocker.Mock()
    response.json.return_value = {"script": encoded}

    mocker.patch.object(exporter, "make_http_request", return_value=response)
    mocker.patch.object(exporter, "build_auth_headers", return_value={})

    data = exporter.fetch_script_data("script1", "token", "https://base")

    assert data["script"] == ["print('hi')"]


def test_fetch_script_data_forbidden_returns_empty(mocker):
    exporter = OAuthExporter()
    mocker.patch.object(
        exporter, "make_http_request", side_effect=Exception("403 Forbidden")
    )

    data = exporter.fetch_script_data("script1", "token", "https://base")

    assert data == {}


def test_export_oauth_happy_path(mocker):
    export_oauth = create_oauth_export_command()

    mock_exporter = mocker.Mock(spec=OAuthExporter)
    mocker.patch("trxo.commands.export.oauth.OAuthExporter", return_value=mock_exporter)

    mock_exporter.initialize_auth.return_value = ("token", "https://base")
    mock_exporter._construct_api_url.return_value = "https://base/list"
    mock_exporter.build_auth_headers.return_value = {}
    mock_exporter._get_storage_mode.return_value = "local"

    response = mocker.Mock()
    response.json.return_value = {"result": [{"_id": "client1", "scriptA": "script1"}]}

    mock_exporter.make_http_request.return_value = response

    mock_exporter.fetch_oauth_client_data.return_value = {
        "_id": "client1",
        "scriptA": "script1",
    }

    mock_exporter.extract_script_ids.return_value = {"script1"}

    mock_exporter.fetch_script_data.return_value = {
        "_id": "script1",
        "script": "ZXhhbXBsZQ==",
    }

    mock_exporter.save_response.return_value = "/tmp/file.json"

    mock_exporter.hash_manager = mocker.Mock()
    mock_exporter.hash_manager.create_hash.return_value = "hash"
    mock_exporter.hash_manager.save_export_hash.return_value = None

    export_oauth(view=False)

    mock_exporter.initialize_auth.assert_called_once()
    mock_exporter.fetch_oauth_client_data.assert_called_once_with(
        "client1", "token", "https://base"
    )
    mock_exporter.fetch_script_data.assert_called_once_with(
        "script1", "token", "https://base"
    )
    mock_exporter.save_response.assert_called_once()
    mock_exporter.hash_manager.create_hash.assert_called_once()
    mock_exporter.hash_manager.save_export_hash.assert_called_once()
