import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from trxo.utils.export.git_export_handler import GitExportHandler


@pytest.fixture
def fake_config_store(mocker):
    store = MagicMock()
    store.get_current_project.return_value = "proj1"
    store.get_git_credentials.return_value = {
        "username": "u",
        "repo_url": "https://example.com/repo.git",
        "token": "t",
    }
    return store


@pytest.fixture
def fake_git_manager(tmp_path):
    mgr = MagicMock()
    mgr.local_path = tmp_path
    mgr.commit_and_push.return_value = True
    mgr.get_current_branch.return_value = "main"
    return mgr


def test_setup_git_repo_success(mocker, fake_config_store, fake_git_manager):
    mocker.patch(
        "trxo.utils.export.git_export_handler.setup_git_for_export",
        return_value=fake_git_manager,
    )

    handler = GitExportHandler(fake_config_store)
    mgr = handler.setup_git_repo(branch="dev")

    assert mgr == fake_git_manager
    fake_config_store.get_current_project.assert_called_once()
    fake_config_store.get_git_credentials.assert_called_once_with("proj1")


def test_setup_git_repo_missing_credentials(mocker):
    store = MagicMock()
    store.get_current_project.return_value = "proj1"
    store.get_git_credentials.return_value = None

    mocker.patch("trxo.utils.export.git_export_handler.error")

    handler = GitExportHandler(store)

    with pytest.raises(ValueError):
        handler.setup_git_repo()


def test_extract_realm_and_component_basic():
    data = {"metadata": {"realm": "alpha"}}
    realm, component = GitExportHandler.extract_realm_and_component(data, "journeys")

    assert realm == "alpha"
    assert component == "journeys"


def test_extract_realm_and_component_services_realm():
    data = {"metadata": {}}
    realm, component = GitExportHandler.extract_realm_and_component(
        data, "services_realm_beta"
    )

    assert realm == "beta"
    assert component == "services"


def test_create_commit_message_contains_fields(tmp_path):
    data = {
        "metadata": {"api_version": "2.2"},
        "data": {"result": [{"id": 1}, {"id": 2}]},
    }

    msg = GitExportHandler.create_commit_message(
        realm="alpha",
        component="journeys",
        file_path=Path("alpha/journeys/file.json"),
        data=data,
    )

    assert "Realm: alpha" in msg
    assert "Component: journeys" in msg
    assert "Items: 2" in msg
    assert "API Version: 2.2" in msg


def test_save_to_git_success(mocker, fake_config_store, fake_git_manager, tmp_path):
    handler = GitExportHandler(fake_config_store)

    mocker.patch.object(handler, "setup_git_repo", return_value=fake_git_manager)
    mocker.patch("trxo.utils.export.git_export_handler.tqdm", autospec=True)
    mocker.patch("trxo.utils.export.git_export_handler.time.sleep")
    mocker.patch("trxo.utils.export.git_export_handler.info")

    data = {"data": [{"id": 1}], "metadata": {"realm": "alpha"}}

    path = handler.save_to_git(
        data=data,
        command_name="journeys",
        output_file="out",
        branch="dev",
    )

    assert path is not None
    saved_path = Path(path)
    assert saved_path.exists()
    assert saved_path.name == "out.json"

    fake_git_manager.commit_and_push.assert_called_once()
