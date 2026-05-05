import json
import pytest
from unittest.mock import MagicMock, patch
from trxo_lib.imports.domains.services import (
    ServicesImporter,
    ServicesImportService
)

@pytest.fixture
def global_importer():
    return ServicesImporter(scope="global")

@pytest.fixture
def realm_importer():
    return ServicesImporter(scope="realm", realm="alpha")

def test_get_api_endpoint(global_importer, realm_importer):
    assert "global-config" in global_importer.get_api_endpoint("s1", "http://base")
    assert "realms/root/realms/alpha" in realm_importer.get_api_endpoint("s1", "http://base")

def test_get_item_identifier(global_importer):
    item = {"_type": {"_id": "type1"}}
    assert global_importer._get_item_identifier(item) == "type1"

def test_update_item_global_success(global_importer, mocker):
    mocker.patch.object(global_importer, "make_http_request")
    mocker.patch.object(global_importer, "build_auth_headers", return_value={})
    item = {"_id": "s1", "config": "v"}
    res = global_importer.update_item(item, "token", "url")
    assert res is True
    global_importer.make_http_request.assert_called_with(mocker.ANY, "PUT", mocker.ANY, mocker.ANY)

def test_update_item_realm_upsert(realm_importer, mocker):
    mocker.patch.object(realm_importer, "build_auth_headers", return_value={})
    # Mock PUT failing, POST action=create succeeding
    mocker.patch.object(realm_importer, "make_http_request", side_effect=[
        Exception("404"),
        MagicMock(status_code=200)
    ])
    
    item = {"_id": "s1", "config": "v"}
    res = realm_importer.update_item(item, "token", "url")
    assert res is True
    assert realm_importer.make_http_request.call_count == 2
    # Verify second call is POST with action=create
    args = realm_importer.make_http_request.call_args_list[1][0]
    assert args[1] == "POST"
    assert "_action=create" in args[0]

def test_update_item_with_descendants(realm_importer, mocker):
    mocker.patch.object(realm_importer, "build_auth_headers", return_value={})
    mock_req = mocker.patch.object(realm_importer, "make_http_request")
    
    # Mock schema response for descendant
    mock_schema_resp = MagicMock(status_code=200)
    mock_schema_resp.json.return_value = {"properties": {"newProp": {"type": "string"}}}
    mock_req.side_effect = [
        None, # PUT service
        mock_schema_resp, # schema fetch
        None # PUT descendant
    ]
    
    item = {
        "_id": "s1",
        "nextDescendents": [
            {"_id": "d1", "_type": {"_id": "dtype1"}}
        ]
    }
    res = realm_importer.update_item(item, "token", "url")
    assert res is True
    # Initial PUT + Schema + Descendant PUT = 3 calls
    assert mock_req.call_count == 3

def test_services_import_service():
    with patch("trxo_lib.imports.domains.services.ServicesImporter") as mock_imp_class:
        mock_imp = mock_imp_class.return_value
        service = ServicesImportService(file="f.json", scope="global")
        service.execute()
        mock_imp.import_from_file.assert_called_with(file_path="f.json", realm="global")
