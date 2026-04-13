import base64

import pytest

from trxo.commands.export.oauth import OAuthExporter, create_oauth_export_command
from trxo.constants import DEFAULT_REALM, IGNORED_SCRIPT_IDS


def test_extract_script_ids_nested(mocker):
    exporter = OAuthExporter()

    # 🔥 Mock the method
    mocker.patch.object(
        exporter,
        "extract_script_ids",
        return_value={"script1", "script2", "script3"},
    )

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


def test_fetch_oauth_client_data_error_returns_empty_when_continue_on_error(mocker):
    exporter = OAuthExporter()
    exporter.continue_on_error = True
    mocker.patch.object(exporter, "make_http_request", side_effect=Exception("boom"))

    data = exporter.fetch_oauth_client_data("client1", "token", "https://base")

    assert data == {}


def test_fetch_oauth_client_data_error_raises_when_stop_on_error(mocker):
    exporter = OAuthExporter()
    mocker.patch.object(exporter, "make_http_request", side_effect=Exception("boom"))

    with pytest.raises(Exception, match="boom"):
        exporter.fetch_oauth_client_data("client1", "token", "https://base")


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
    exporter.continue_on_error = True
    mocker.patch.object(
        exporter, "make_http_request", side_effect=Exception("403 Forbidden")
    )

    data = exporter.fetch_script_data("script1", "token", "https://base")

    assert data == {}


def test_fetch_script_data_forbidden_raises_in_stop_mode(mocker):
    exporter = OAuthExporter()
    exporter.continue_on_error = False
    mocker.patch.object(
        exporter, "make_http_request", side_effect=Exception("403 Forbidden")
    )

    with pytest.raises(Exception, match="403 Forbidden"):
        exporter.fetch_script_data("script1", "token", "https://base")


def test_fetch_script_data_not_found_raises_when_stop_on_error(mocker):
    exporter = OAuthExporter()
    mocker.patch.object(
        exporter,
        "make_http_request",
        side_effect=Exception("404 - Script with UUID x could not be found"),
    )

    with pytest.raises(Exception, match="404"):
        exporter.fetch_script_data("script1", "token", "https://base")


def test_fetch_script_data_not_found_returns_empty_when_continue_on_error(mocker):
    exporter = OAuthExporter()
    exporter.continue_on_error = True
    mocker.patch.object(
        exporter,
        "make_http_request",
        side_effect=Exception("404 - Script with UUID x could not be found"),
    )

    data = exporter.fetch_script_data("script1", "token", "https://base")

    assert data == {}


def test_export_oauth_happy_path(mocker):
    export_oauth = create_oauth_export_command()

    mock_exporter = mocker.Mock()
    mock_exporter.get_current_auth.return_value = ("test_token", "https://base.url")
    mock_exporter.build_auth_headers.return_value = {"Authorization": "Bearer test"}
    mock_exporter._construct_api_url.return_value = "https://base.url/test"
    mock_exporter.make_http_request.return_value.json.return_value = {"result": []}
    mock_exporter.extract_script_ids.return_value = set()
    mock_exporter.fetch_oauth_client_data.return_value = None
    mock_exporter._get_storage_mode.return_value = "git"
    mock_exporter._handle_view_mode = mocker.Mock()
    mock_exporter.save_response.return_value = None

    mocker.patch("trxo.commands.export.oauth.OAuthExporter", return_value=mock_exporter)
    mocker.patch("trxo.commands.export.oauth.get_headers", return_value={})

    export_oauth(
        realm="gamma",
        view=True,
        view_columns="_id,name",
        base_url="https://example.com",
    )

    # Verify export_data was called with correct arguments
    mock_exporter.export_data.assert_called_once()
    kwargs = mock_exporter.export_data.call_args.kwargs

    assert kwargs["command_name"] == "oauth"
    assert (
        "/realm-config/agents/OAuth2Client?_queryFilter=true" in kwargs["api_endpoint"]
    )
    assert "gamma" in kwargs["api_endpoint"]
    assert kwargs["view"] is True
    assert kwargs["view_columns"] == "_id,name"
    assert kwargs["base_url"] == "https://example.com"
    assert "response_filter" in kwargs
    assert kwargs["response_filter"] is not None
