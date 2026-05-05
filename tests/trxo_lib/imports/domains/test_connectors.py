import json
import pytest
from unittest.mock import MagicMock, patch, mock_open
from trxo_lib.imports.domains.connectors import (
    ConnectorsImporter,
    ConnectorsImportService
)

@pytest.fixture
def connectors_importer():
    return ConnectorsImporter()

def test_load_data_from_file_result(connectors_importer):
    mock_data = {"data": {"result": [{"_id": "c1"}]}}
    with patch("builtins.open", mock_open(read_data=json.dumps(mock_data))):
        res = connectors_importer.load_data_from_file("f.json")
        assert res == [{"_id": "c1"}]

def test_update_item_success(connectors_importer):
    with patch("httpx.Client") as mock_client:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client.return_value.__enter__.return_value.put.return_value = mock_resp
        
        res = connectors_importer.update_item({"_id": "c1", "val": "x"}, "token", "url")
        assert res is True

def test_update_item_failure(connectors_importer):
    with patch("httpx.Client") as mock_client:
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_client.return_value.__enter__.return_value.put.return_value = mock_resp
        
        res = connectors_importer.update_item({"_id": "c1"}, "token", "url")
        assert res is False

def test_delete_item_success(connectors_importer):
    connectors_importer.make_http_request = MagicMock()
    connectors_importer.build_auth_headers = MagicMock(return_value={})
    assert connectors_importer.delete_item("c1", "token", "url") is True

def test_import_from_git_success(connectors_importer):
    connectors_importer._setup_git_manager = MagicMock()
    connectors_importer.file_loader = MagicMock()
    # Mock nested data format
    connectors_importer.file_loader.load_git_files.return_value = [
        {"data": {"result": [{"_id": "c1"}]}},
        [{"_id": "c2"}],
        {"_id": "c3"}
    ]
    
    res = connectors_importer._import_from_git("alpha", False)
    assert len(res) == 3
    assert res[0]["_id"] == "c1"
    assert res[1]["_id"] == "c2"
    assert res[2]["_id"] == "c3"

def test_load_data_from_git(connectors_importer):
    connectors_importer.file_loader = MagicMock()
    connectors_importer.file_loader.load_git_files.return_value = [{"data": {"result": [{"_id": "c1"}]}}]
    res = connectors_importer.load_data_from_git(MagicMock(), "type", "realm", "branch")
    assert res == [{"_id": "c1"}]

def test_delete_item_failure(connectors_importer):
    connectors_importer.make_http_request = MagicMock(side_effect=Exception("fail"))
    connectors_importer.build_auth_headers = MagicMock(return_value={})
    assert connectors_importer.delete_item("c1", "token", "url") is False

def test_getters(connectors_importer):
    assert connectors_importer.get_required_fields() == ["_id"]
    assert connectors_importer.get_item_type() == "connectors"

def test_connectors_import_service():
    with patch("trxo_lib.imports.domains.connectors.ConnectorsImporter") as mock_imp_class:
        mock_imp = mock_imp_class.return_value
        service = ConnectorsImportService(file="f.json")
        service.execute()
        mock_imp.import_from_file.assert_called_with(file_path="f.json", realm=None)
