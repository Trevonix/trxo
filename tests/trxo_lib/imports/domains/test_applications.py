import json
import pytest
from unittest.mock import MagicMock, patch, mock_open
from trxo_lib.imports.domains.applications import (
    _normalize_dep_block,
    _normalize_provider_block,
    ApplicationsImporter,
    ApplicationsImportService
)

def test_normalize_dep_block():
    assert _normalize_dep_block([{"_id": "1"}, "not-a-dict"]) == [{"_id": "1"}]
    assert _normalize_dep_block({"k1": {"_id": "1"}}) == [{"_id": "1"}]
    assert _normalize_dep_block(None) == []

def test_normalize_provider_block():
    assert _normalize_provider_block({"_type": {"_id": "t"}}) == [{"_type": {"_id": "t"}}]
    assert _normalize_provider_block([{"val": 1}]) == [{"val": 1}]
    assert _normalize_provider_block(None) == []

def test_load_data_from_file_with_deps():
    importer = ApplicationsImporter(realm="alpha")
    importer.include_am_dependencies = True
    
    mock_data = {
        "data": {
            "applications": [{"_id": "app1"}],
            "clients": [{"_id": "c1", "_provider": {"_id": "p1"}}],
            "scripts": [{"_id": "s1"}],
            "providers": [{"_id": "p2"}]
        }
    }
    
    with patch("builtins.open", mock_open(read_data=json.dumps(mock_data))):
        with patch("os.path.abspath", side_effect=lambda x: x):
            items = importer.load_data_from_file("file.json")
            assert items == [{"_id": "app1"}]
            assert len(importer._pending_clients) == 1
            assert len(importer._pending_scripts) == 1
            # p1 (from client) + p2 (from providers)
            assert len(importer._pending_providers) == 2

def test_process_items_with_deps():
    importer = ApplicationsImporter(realm="alpha")
    importer.include_am_dependencies = True
    importer._pending_scripts = [{"_id": "s1"}]
    importer._pending_providers = [{"_id": "p1"}]
    importer._pending_clients = [{"_id": "c1"}]
    
    with patch("trxo_lib.imports.domains.applications.ScriptImporter") as mock_script_imp:
        with patch("trxo_lib.imports.domains.applications.OAuthImporter") as mock_oauth_imp:
            mock_oauth = mock_oauth_imp.return_value
            importer.process_items([], "token", "url")
            
            mock_script_imp.return_value.process_items.assert_called()
            mock_oauth.update_provider.assert_called()
            mock_oauth.update_item.assert_called()

def test_update_item_success():
    importer = ApplicationsImporter(realm="alpha")
    importer.make_http_request = MagicMock()
    importer.build_auth_headers = MagicMock(return_value={"Auth": "token"})
    
    res = importer.update_item({"_id": "app1", "name": "App"}, "token", "url")
    assert res is True
    # Verify it was called with the auth header merged in
    args = importer.make_http_request.call_args[0]
    assert args[2]["Auth"] == "token"
    assert "application/json" in args[2]["Content-Type"]

def test_delete_item_success():
    importer = ApplicationsImporter(realm="alpha")
    importer.make_http_request = MagicMock()
    importer.build_auth_headers = MagicMock(return_value={})
    assert importer.delete_item("app1", "token", "url") is True
    from unittest.mock import ANY
    importer.make_http_request.assert_called_with("url/openidm/managed/alpha_application/app1", "DELETE", ANY)

def test_import_from_git_success():
    importer = ApplicationsImporter(realm="alpha")
    importer._setup_git_manager = MagicMock()
    importer._setup_git_manager.return_value.local_path = "/repo"
    importer.file_loader = MagicMock()
    importer.file_loader.discover_git_files.return_value = [MagicMock()] # 1 file
    
    with patch.object(importer, "load_data_from_file", return_value=[{"_id": "a1"}]):
        res = importer._import_from_git("alpha", False)
        assert len(res) == 1
        assert res[0]["_id"] == "a1"

def test_update_item_missing_id():
    importer = ApplicationsImporter(realm="alpha")
    assert importer.update_item({}, "token", "url") is False

def test_applications_import_service():
    with patch("trxo_lib.imports.domains.applications.ApplicationsImporter") as mock_imp_class:
        mock_imp = mock_imp_class.return_value
        service = ApplicationsImportService(file="file.json", with_deps=True)
        service.execute()
        assert mock_imp.include_am_dependencies is True
        mock_imp.import_from_file.assert_called_with(file_path="file.json")
