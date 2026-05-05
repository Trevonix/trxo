import json
import pytest
from unittest.mock import MagicMock, patch
from trxo_lib.imports.domains.journeys import JourneyImporter

@pytest.fixture
def importer():
    return JourneyImporter(realm="alpha")

def test_get_api_endpoint(importer):
    assert "authenticationtrees/trees/t1" in importer.get_api_endpoint("t1", "http://base")

def test_load_data_from_file_enriched(importer, tmp_path):
    data = {"data": {"trees": {"t1": {"_id": "t1"}}}}
    f = tmp_path / "enriched.json"
    f.write_text(json.dumps(data))
    res = importer.load_data_from_file(str(f))
    assert len(res) == 1
    assert res[0]["_id"] == "t1"

def test_load_data_from_file_legacy(importer, tmp_path):
    data = {"data": [{"_id": "t1"}]}
    f = tmp_path / "legacy.json"
    f.write_text(json.dumps(data))
    res = importer.load_data_from_file(str(f))
    assert len(res) == 1
    assert res[0]["_id"] == "t1"

def test_setup_enriched_rollback_managers(importer, mocker):
    mocker.patch.object(importer, "_get_storage_mode", return_value="local")
    mock_mgr_class = mocker.patch("trxo_lib.state.rollback.RollbackManager")
    mock_mgr = mock_mgr_class.return_value
    mock_mgr.create_baseline_snapshot.return_value = True
    
    managers = importer._setup_enriched_rollback_managers(True, None, "token", "url")
    assert "trees" in managers
    assert "scripts" in managers
    assert len(managers) == 6

def test_import_journey_data_orchestration(importer, mocker):
    mocker.patch.object(importer, "_import_single_script", return_value=True)
    mocker.patch.object(importer, "_import_email_template", return_value=True)
    mocker.patch.object(importer, "_import_saml_entity", return_value=True)
    mocker.patch.object(importer, "_import_circle_of_trust", return_value=True)
    mocker.patch.object(importer, "_import_node", return_value=True)
    mocker.patch.object(importer, "_import_themes", return_value=True)
    mocker.patch.object(importer, "update_item", return_value=True)
    
    data = {
        "scripts": {"s1": {}},
        "emailTemplates": {"e1": {}},
        "trees": {"t1": {}}
    }
    res = importer.import_journey_data(data, "token", "url")
    assert res is True
    assert importer._import_single_script.called
    assert importer.update_item.called

def test_import_node_success(importer, mocker):
    mocker.patch.object(importer, "build_auth_headers", return_value={})
    mocker.patch.object(importer, "make_http_request")
    
    node_cfg = {"_id": "n1", "_type": {"_id": "type1"}}
    res = importer._import_node("n1", node_cfg, "token", "url")
    assert res is True
    # Verify URL contains node type
    args = importer.make_http_request.call_args[0]
    assert "authenticationtrees/nodes/type1/n1" in args[0]

def test_import_themes_success(importer, mocker):
    mocker.patch.object(importer, "build_auth_headers", return_value={})
    mock_themes_imp = mocker.Mock()
    mock_themes_imp.update_item.return_value = True
    mocker.patch("trxo_lib.imports.domains.journeys._themes_importer", return_value=mock_themes_imp)
    
    themes = {"theme1": {"_id": "theme1"}}
    res = importer._import_themes(themes, "token", "url")
    assert res is True
    mock_themes_imp.update_item.assert_called_once()
