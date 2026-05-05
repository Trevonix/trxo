import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from trxo.utils.export.git_export_handler import GitExportHandler
from trxo_lib.exceptions import TrxoConfigError, TrxoGitError

@pytest.fixture
def mock_config_store(mocker):
    return mocker.Mock()

@pytest.fixture
def handler(mock_config_store):
    return GitExportHandler(mock_config_store)

def test_extract_realm_and_component_metadata():
    data = {"metadata": {"realm": "alpha"}}
    realm, comp = GitExportHandler.extract_realm_and_component(data, "saml")
    assert realm == "alpha"
    assert comp == "saml"

def test_extract_realm_and_component_services_realm():
    data = {}
    realm, comp = GitExportHandler.extract_realm_and_component(data, "services_realm_beta")
    assert realm == "beta"
    assert comp == "services"

def test_extract_realm_and_component_services_global():
    data = {}
    realm, comp = GitExportHandler.extract_realm_and_component(data, "services_global")
    assert realm == "global"
    assert comp == "services"

def test_create_commit_message():
    data = {
        "data": {"result": [{"id": 1}, {"id": 2}]},
        "metadata": {"api_version": "2.0"}
    }
    msg = GitExportHandler.create_commit_message("alpha", "saml", Path("file.json"), data)
    assert "Realm: alpha" in msg
    assert "Items: 2" in msg
    assert "API Version: 2.0" in msg

def test_setup_git_repo_success(handler, mock_config_store, mocker):
    mock_config_store.get_current_project.return_value = "p1"
    mock_config_store.get_git_credentials.return_value = {
        "username": "u", "repo_url": "url", "token": "t"
    }
    mock_setup = mocker.patch("trxo.utils.export.git_export_handler.setup_git_for_export")
    
    handler.setup_git_repo("dev")
    mock_setup.assert_called_once_with("u", "t", "url", "dev")

def test_setup_git_repo_missing_credentials(handler, mock_config_store):
    mock_config_store.get_git_credentials.return_value = None
    with pytest.raises(TrxoConfigError, match="Git credentials not found"):
        handler.setup_git_repo()

def test_save_to_git_success(handler, mocker, tmp_path):
    # Mock GitManager
    mock_gm = mocker.Mock()
    mock_gm.local_path = tmp_path
    mock_gm.commit_and_push.return_value = True
    mock_gm.get_current_branch.return_value = "main"
    
    mocker.patch.object(handler, "setup_git_repo", return_value=mock_gm)
    mocker.patch("trxo.utils.export.git_export_handler.info")
    mocker.patch("time.sleep")
    
    data = {"data": {"result": []}}
    path = handler.save_to_git(data, "saml", branch="main")
    
    assert path is not None
    assert (tmp_path / "root" / "saml" / "root_saml.json").exists()
    mock_gm.commit_and_push.assert_called_once()

def test_save_to_git_no_changes(handler, mocker, tmp_path):
    mock_gm = mocker.Mock()
    mock_gm.local_path = tmp_path
    mock_gm.commit_and_push.return_value = False # No changes
    
    mocker.patch.object(handler, "setup_git_repo", return_value=mock_gm)
    mocker.patch("trxo.utils.export.git_export_handler.info")
    mocker.patch("time.sleep")
    
    data = {}
    path = handler.save_to_git(data, "saml")
    assert path is not None
    mock_gm.commit_and_push.assert_called_once()

def test_save_to_git_exception(handler, mocker):
    mocker.patch.object(handler, "setup_git_repo", side_effect=Exception("boom"))
    with pytest.raises(TrxoGitError, match="Failed to save to Git"):
        handler.save_to_git({}, "saml")
