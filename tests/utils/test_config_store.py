import json
import os
import platform
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from trxo.utils.config_store import ConfigStore, SERVICE_NAME


@pytest.fixture
def temp_config_dir(tmp_path, mocker):
    mocker.patch("platform.system", return_value="Linux")
    mocker.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path)})
    return tmp_path


@pytest.fixture
def store(temp_config_dir):
    return ConfigStore()


def test_get_config_dir_linux_xdg(temp_config_dir, mocker):
    mocker.patch("platform.system", return_value="Linux")
    mocker.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(temp_config_dir)})

    store = ConfigStore()
    assert store.base_dir == temp_config_dir / "trxo"


def test_get_config_dir_linux_fallback(tmp_path, mocker):
    mocker.patch("platform.system", return_value="Linux")
    mocker.patch.dict(os.environ, {}, clear=True)
    mocker.patch("pathlib.Path.home", return_value=tmp_path)

    store = ConfigStore()
    assert store.base_dir == tmp_path / ".trxo"


def test_get_config_dir_windows(tmp_path, mocker):
    mocker.patch("platform.system", return_value="Windows")
    mocker.patch.dict(os.environ, {"APPDATA": str(tmp_path)})

    store = ConfigStore()
    assert store.base_dir == tmp_path / "trxo"


def test_get_config_dir_macos(tmp_path, mocker):
    mocker.patch("platform.system", return_value="Darwin")
    mocker.patch("pathlib.Path.home", return_value=tmp_path)

    store = ConfigStore()
    assert store.base_dir == tmp_path / "Library" / "Application Support" / "trxo"


def test_save_and_get_project(store):
    store.save_project("p1", {"git_repo": "url", "git_username": "u"})
    projects = store.get_projects()
    assert "p1" in projects

    cfg = store.get_project_config("p1")
    assert cfg["git_repo"] == "url"
    assert cfg["git_username"] == "u"


def test_get_projects_file_missing(store):
    store.projects_file.unlink(missing_ok=True)
    assert store.get_projects() == {}


def test_get_projects_corrupted_json(store):
    store.projects_file.write_text("{bad json")
    assert store.get_projects() == {}


def test_get_project_config_missing(store):
    assert store.get_project_config("nope") is None


def test_get_project_config_corrupted_json(store):
    pdir = store.get_project_dir("p1")
    (pdir / "config.json").write_text("{bad")
    assert store.get_project_config("p1") is None


def test_set_and_get_current_project(store):
    store.set_current_project("p1")
    assert store.get_current_project() == "p1"


def test_get_current_project_missing(store):
    store.current_project_file.unlink(missing_ok=True)
    assert store.get_current_project() is None


def test_delete_project(store):
    store.save_project("p1", {"a": 1})
    store.delete_project("p1")

    assert "p1" not in store.get_projects()

    project_path = store.base_dir / "projects" / "p1"
    assert not project_path.exists()


def test_save_and_get_token(store):
    store.save_token("p1", {"access": "tok"})
    token = store.get_token("p1")
    assert token["access"] == "tok"


def test_get_token_missing(store):
    assert store.get_token("nope") is None


def test_get_token_corrupted(store):
    pdir = store.get_project_dir("p1")
    (pdir / "token.json").write_text("{bad")
    assert store.get_token("p1") is None


def test_store_git_credentials_keyring(mocker, store):
    set_pw = mocker.patch("keyring.set_password")

    store.store_git_credentials("p1", "u", "url", "tok")

    set_pw.assert_any_call("trxo:p1:git_token", "token", "tok")
    set_pw.assert_any_call(SERVICE_NAME, "token", "tok")


def test_get_git_credentials_scoped(mocker, store):
    store.save_project("p1", {"git_repo": "url", "git_username": "u"})

    get_pw = mocker.patch(
        "keyring.get_password",
        side_effect=lambda s, k: {"trxo:p1:git_token": "tok"}.get(s),
    )

    creds = store.get_git_credentials("p1")

    assert creds == {"username": "u", "repo_url": "url", "token": "tok"}


def test_get_git_credentials_fallback_global(mocker, store):
    store.save_project("p1", {"git_repo": None, "git_username": None})

    def fake_get(service, key):
        data = {SERVICE_NAME: {"token": "tok", "username": "u", "repo_url": "url"}}
        return data.get(service, {}).get(key)

    mocker.patch("keyring.get_password", side_effect=fake_get)

    creds = store.get_git_credentials("p1")
    assert creds == {"username": "u", "repo_url": "url", "token": "tok"}


def test_get_git_credentials_missing_project(store):
    assert store.get_git_credentials("nope") is None


def test_get_git_credentials_missing_all(mocker, store):
    store.save_project("p1", {})
    mocker.patch("keyring.get_password", return_value=None)

    assert store.get_git_credentials("p1") is None
