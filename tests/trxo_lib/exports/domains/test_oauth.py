import pytest
from unittest.mock import MagicMock, patch
from trxo_lib.exports.domains.oauth import (
    process_oauth_response,
    OAuthExporter,
    OauthExportService
)

@pytest.fixture
def oauth_exporter():
    return OAuthExporter(realm="alpha")

def test_extract_script_ids(oauth_exporter):
    data = {
        "authnContextMapperScript": "12345678-1234-1234-1234-123456789012",
        "nested": [{"valScript": "87654321-4321-4321-4321-210987654321"}],
        "empty": "[Empty]",
        "ignored": "short"
    }
    ids = oauth_exporter.extract_script_ids(data)
    assert len(ids) == 2
    assert "12345678-1234-1234-1234-123456789012" in ids

def test_fetch_script_data_success(oauth_exporter):
    mock_resp = MagicMock()
    # Test base64 decode
    mock_resp.json.return_value = {"script": "cHJpbnQoJ2hlbGxvJyk="} # print('hello')
    oauth_exporter.make_http_request = MagicMock(return_value=mock_resp)
    oauth_exporter.build_auth_headers = MagicMock(return_value={})
    
    res = oauth_exporter.fetch_script_data("sid", "token", "http://base")
    assert res["script"] == ["print('hello')"]

def test_fetch_script_data_forbidden(oauth_exporter):
    oauth_exporter.make_http_request = MagicMock(side_effect=Exception("403 Forbidden"))
    oauth_exporter.build_auth_headers = MagicMock(return_value={})
    res = oauth_exporter.fetch_script_data("sid", "token", "http://base")
    assert res == {}

def test_fetch_oauth_client_data_success(oauth_exporter):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"_id": "c1", "_rev": "r1", "name": "Client"}
    oauth_exporter.make_http_request = MagicMock(return_value=mock_resp)
    oauth_exporter.build_auth_headers = MagicMock(return_value={})
    
    res = oauth_exporter.fetch_oauth_client_data("c1", "token", "http://base")
    assert res == {"_id": "c1", "name": "Client"} # _rev should be popped

def test_discover_provider_service_endpoints(oauth_exporter):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [{"_id": "oauth2Provider"}]}
    oauth_exporter.make_http_request = MagicMock(return_value=mock_resp)
    oauth_exporter.build_auth_headers = MagicMock(return_value={})
    
    eps = oauth_exporter._discover_provider_service_endpoints("token", "http://base")
    assert len(eps) == 1
    assert "oauth2Provider" in eps[0]

def test_fetch_oauth_provider_data_success(oauth_exporter):
    oauth_exporter._discover_provider_service_endpoints = MagicMock(return_value=["/ep1"])
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"_id": "p1", "_rev": "r1"}
    oauth_exporter.make_http_request = MagicMock(return_value=mock_resp)
    oauth_exporter.build_auth_headers = MagicMock(return_value={})
    
    res = oauth_exporter.fetch_oauth_provider_data("token", "http://base")
    assert res == {"_id": "p1"}

def test_process_oauth_response_success(oauth_exporter):
    oauth_exporter.get_current_auth = MagicMock(return_value=("token", "http://base"))
    oauth_exporter.fetch_oauth_client_data = MagicMock(return_value={"_id": "c1"})
    oauth_exporter.extract_script_ids = MagicMock(return_value=["s1"])
    oauth_exporter.fetch_script_data = MagicMock(return_value={"_id": "s1"})
    oauth_exporter.build_auth_headers = MagicMock(return_value={})
    
    filter_func = process_oauth_response(oauth_exporter, "alpha")
    res = filter_func({"result": [{"_id": "c1"}]})
    assert len(res["clients"]) == 1
    assert len(res["scripts"]) == 1

def test_fetch_script_data_404(oauth_exporter):
    oauth_exporter.make_http_request = MagicMock(side_effect=Exception("404 Not Found"))
    oauth_exporter.build_auth_headers = MagicMock(return_value={})
    res = oauth_exporter.fetch_script_data("sid", "token", "http://base")
    assert res == {}

def test_fetch_script_data_decode_error(oauth_exporter):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"script": "invalid-base64"}
    oauth_exporter.make_http_request = MagicMock(return_value=mock_resp)
    oauth_exporter.build_auth_headers = MagicMock(return_value={})
    res = oauth_exporter.fetch_script_data("sid", "token", "http://base")
    assert res["script"] == "invalid-base64"

def test_discover_provider_service_endpoints_empty(oauth_exporter):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": []}
    oauth_exporter.make_http_request = MagicMock(return_value=mock_resp)
    oauth_exporter.build_auth_headers = MagicMock(return_value={})
    assert oauth_exporter._discover_provider_service_endpoints("t", "u") == []

def test_fetch_oauth_provider_data_no_eps(oauth_exporter):
    oauth_exporter._discover_provider_service_endpoints = MagicMock(return_value=[])
    assert oauth_exporter.fetch_oauth_provider_data("t", "u") == {}

def test_fetch_oauth_provider_data_all_fail(oauth_exporter):
    oauth_exporter._discover_provider_service_endpoints = MagicMock(return_value=["/ep"])
    oauth_exporter.make_http_request = MagicMock(side_effect=Exception("fail"))
    oauth_exporter.build_auth_headers = MagicMock(return_value={})
    assert oauth_exporter.fetch_oauth_provider_data("t", "u") == {}

def test_process_oauth_response_invalid(oauth_exporter):
    filter_func = process_oauth_response(oauth_exporter, "alpha")
    res = filter_func({})
    assert res["clients"] == []

def test_oauth_export_service_commit_mapping():
    with patch("trxo_lib.exports.domains.oauth.OAuthExporter") as mock_exporter_class:
        mock_exporter = mock_exporter_class.return_value
        service = OauthExportService(realm="alpha", commit="msg")
        service.execute()
        args = mock_exporter.export_data.call_args[1]
        assert args["commit_message"] == "msg"
