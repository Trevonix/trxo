import json
import base64
import pytest
from unittest.mock import MagicMock, patch
from trxo_lib.imports.domains.saml import SamlImporter, SamlImportService

@pytest.fixture
def importer():
    return SamlImporter(realm="alpha")

def test_get_api_endpoint(importer):
    assert "realm-config/saml2" in importer.get_api_endpoint("id", "http://base")

def test_extract_script_ids_from_config(importer):
    config = {
        "mapperScript": "12345678-1234-1234-1234-123456789012",
        "nested": [{"otherScript": "87654321-4321-4321-4321-210987654321"}]
    }
    ids = importer._extract_script_ids_from_config(config)
    assert len(ids) == 2
    assert "12345678-1234-1234-1234-123456789012" in ids

def test_import_single_script_success(importer, mocker):
    mocker.patch.object(importer, "make_http_request")
    mocker.patch.object(importer, "build_auth_headers", return_value={})
    
    script_data = {
        "_id": "s1",
        "name": "Script 1",
        "script": ["print('hello')", "print('world')"]
    }
    res = importer._import_single_script(script_data, "token", "url")
    assert res is True
    # Check if script was base64 encoded
    args = importer.make_http_request.call_args[0]
    payload = json.loads(args[3])
    assert payload["script"] == base64.b64encode(b"print('hello')\nprint('world')").decode("ascii")

def test_import_single_metadata_exists(importer, mocker):
    mocker.patch.object(importer, "build_auth_headers", return_value={})
    mock_resp = MagicMock()
    mock_resp.text = "Metadata content"
    mocker.patch.object(importer, "make_http_request", return_value=mock_resp)
    
    res = importer._import_single_metadata("entity1", "<xml/>", "token", "url")
    assert res is None # info() is called, returns None if not posting
    # Wait, _import_single_metadata returns None if metadata exists? 
    # Actually it doesn't have a return statement at the end of the 'else' block.
    # Lines 563-564: info("Metadata exists for '{entity_id}'")
    
def test_post_metadata_success(importer, mocker):
    mocker.patch.object(importer, "make_http_request")
    mocker.patch.object(importer, "build_auth_headers", return_value={})
    
    res = importer._post_metadata("entity1", "<xml/>", "token", "url")
    assert res is True
    args = importer.make_http_request.call_args[0]
    assert args[1] == "POST"
    assert "_action=importEntity" in args[0]

def test_upsert_hosted_entity_create(importer, mocker):
    mocker.patch.object(importer, "build_auth_headers", return_value={})
    
    # Mock PUT failing with 404, then POST create succeeding
    mock_resp_404 = MagicMock(status_code=404)
    mocker.patch("httpx.Client.put", return_value=mock_resp_404)
    mocker.patch.object(importer, "make_http_request")
    
    entity = {"_id": "h1", "entityId": "hosted1"}
    res = importer._upsert_entity(entity, "hosted", "token", "url")
    assert res is True
    importer.make_http_request.assert_called()
    assert "_action=create" in importer.make_http_request.call_args[0][0]

def test_import_saml_data_orchestration(importer, mocker):
    mocker.patch.object(importer, "_import_scripts", return_value=True)
    mocker.patch.object(importer, "_import_metadata", return_value=True)
    mocker.patch.object(importer, "_upsert_entity", return_value=True)
    
    data = {
        "scripts": [{"_id": "s1"}],
        "hosted": [{"_id": "h1"}],
        "remote": [{"_id": "r1"}],
        "metadata": [{"entityId": "r1", "xml": "<xml/>"}]
    }
    res = importer.import_saml_data(data, "token", "url")
    assert res is True
    assert importer._upsert_entity.call_count == 2
