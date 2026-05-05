import json
import pytest
from unittest.mock import MagicMock, patch
from trxo_lib.imports.domains.oauth import OAuthImporter

@pytest.fixture
def importer():
    return OAuthImporter(realm="alpha")

def test_parse_oauth_data_standard(importer):
    data = {
        "data": {
            "clients": [{"_id": "c1"}],
            "scripts": [{"_id": "s1"}]
        }
    }
    clients = importer._parse_oauth_data(data)
    assert len(clients) == 1
    assert len(importer._pending_scripts) == 1

def test_process_items_with_scripts(importer, mocker):
    mocker.patch.object(importer.script_importer, "process_items")
    mocker.patch.object(importer, "update_item", return_value=True)
    mocker.patch.object(importer, "initialize_auth", return_value=("token", "url"))
    
    mock_rb = mocker.Mock()
    mock_rb.baseline_snapshot = {}
    
    importer._pending_scripts = [{"_id": "s1"}]
    items = [{"_id": "c1"}]
    
    importer.process_items(items, "token", "url", rollback_manager=mock_rb)
    assert importer.script_importer.process_items.called
    assert len(importer._pending_scripts) == 0

def test_update_item_success(importer, mocker):
    mocker.patch.object(importer, "build_auth_headers", return_value={})
    mock_resp = mocker.Mock(status_code=200)
    mocker.patch.object(importer, "make_http_request", return_value=mock_resp)
    
    res = importer.update_item({"_id": "c1"}, "token", "url")
    assert res is True
    assert importer.make_http_request.call_args[0][1] == "PUT"

def test_update_provider_success(importer, mocker):
    mocker.patch.object(importer, "build_auth_headers", return_value={})
    # Mock services list response to return an OAuth service
    mock_list_resp = MagicMock()
    mock_list_resp.json.return_value = {"result": [{"_id": "oauth-oidc"}]}
    mocker.patch.object(importer, "make_http_request", side_effect=[
        mock_list_resp, # services list
        MagicMock(status_code=200) # PUT provider
    ])
    
    res = importer.update_provider({"issuer": "http://iss"}, "token", "url")
    assert res is True
    assert importer.make_http_request.call_count == 2

def test_delete_item_success(importer, mocker):
    mocker.patch.object(importer, "build_auth_headers", return_value={})
    mocker.patch.object(importer, "make_http_request")
    
    res = importer.delete_item("c1", "token", "url")
    assert res is True
    assert importer.make_http_request.call_args[0][1] == "DELETE"
