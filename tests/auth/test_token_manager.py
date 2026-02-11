import pytest
from unittest.mock import MagicMock

from trxo.auth.token_manager import TokenManager


@pytest.fixture
def store():
    return MagicMock()


@pytest.fixture
def manager(store):
    return TokenManager(store)


def test_get_token_uses_cached_token(mocker, manager, store):
    mocker.patch("trxo.auth.token_manager.time.time", return_value=1000)

    store.get_token.return_value = {
        "access_token": "cached",
        "expires_at": 2000,
    }

    token = manager.get_token("p1")

    assert token == "cached"
    store.get_project_config.assert_not_called()


def test_get_token_missing_project_config(mocker, manager, store):
    mocker.patch("trxo.auth.token_manager.time.time", return_value=1000)
    store.get_token.return_value = None
    store.get_project_config.return_value = None

    error_mock = mocker.patch("trxo.auth.token_manager.error")

    with pytest.raises(ValueError):
        manager.get_token("p1")

    error_mock.assert_called_once()


def test_get_token_missing_auth_config(mocker, manager, store):
    mocker.patch("trxo.auth.token_manager.time.time", return_value=1000)
    store.get_token.return_value = None
    store.get_project_config.return_value = {"client_id": "x"}

    error_mock = mocker.patch("trxo.auth.token_manager.error")

    with pytest.raises(ValueError):
        manager.get_token("p1")

    error_mock.assert_called_once()


def test_get_token_keyring_present(mocker, manager, store):
    mocker.patch("trxo.auth.token_manager.time.time", return_value=1000)
    store.get_token.return_value = None
    store.get_project_config.return_value = {
        "client_id": "cid",
        "sa_id": "sid",
        "token_url": "url",
        "jwk_path": "file.jwk",
    }

    keyring = MagicMock()
    keyring.get_password.return_value = "jwk-content"

    mocker.patch("keyring.get_password", keyring.get_password)

    auth = MagicMock()
    auth.get_access_token.return_value = {
        "access_token": "new",
        "expires_in": 10,
    }

    mocker.patch("trxo.auth.token_manager.ServiceAccountAuth", return_value=auth)

    token = manager.get_token("p1")

    assert token == "new"
    store.save_token.assert_called_once()


def test_get_token_keyring_failure_fallback_to_file(mocker, manager, store):
    mocker.patch("trxo.auth.token_manager.time.time", return_value=1000)
    store.get_token.return_value = None
    store.get_project_config.return_value = {
        "client_id": "cid",
        "sa_id": "sid",
        "token_url": "url",
        "jwk_path": "file.jwk",
    }

    def boom(*args, **kwargs):
        raise Exception("no keyring")

    mocker.patch("keyring.get_password", side_effect=boom)

    auth = MagicMock()
    auth.get_access_token.return_value = {
        "access_token": "new",
        "expires_in": 10,
    }

    mocker.patch("trxo.auth.token_manager.ServiceAccountAuth", return_value=auth)

    token = manager.get_token("p1")

    assert token == "new"
    store.save_token.assert_called_once()


def test_get_token_service_account_error(mocker, manager, store):
    mocker.patch("trxo.auth.token_manager.time.time", return_value=1000)
    store.get_token.return_value = None
    store.get_project_config.return_value = {
        "client_id": "cid",
        "sa_id": "sid",
        "token_url": "url",
        "jwk_path": "file.jwk",
    }

    auth = MagicMock()
    auth.get_access_token.side_effect = Exception("boom")
    mocker.patch("trxo.auth.token_manager.ServiceAccountAuth", return_value=auth)

    error_mock = mocker.patch("trxo.auth.token_manager.error")

    with pytest.raises(Exception):
        manager.get_token("p1")

    error_mock.assert_called_once()
