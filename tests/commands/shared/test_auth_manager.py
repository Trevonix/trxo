import typer
import pytest

from trxo.commands.shared.auth_manager import AuthManager


def test_validate_project_no_project_and_no_args_raises(mocker):
    config_store = mocker.Mock()
    token_manager = mocker.Mock()
    config_store.get_current_project.return_value = None

    manager = AuthManager(config_store, token_manager)

    with pytest.raises(typer.Exit):
        manager.validate_project()


def test_validate_project_returns_current_project(mocker):
    config_store = mocker.Mock()
    token_manager = mocker.Mock()
    config_store.get_current_project.return_value = "proj"

    manager = AuthManager(config_store, token_manager)

    result = manager.validate_project()
    assert result == "proj"


def test_validate_project_service_account_argument_mode(mocker):
    config_store = mocker.Mock()
    token_manager = mocker.Mock()
    config_store.get_current_project.return_value = None

    mocker.patch.object(
        manager := AuthManager(config_store, token_manager),
        "_initialize_argument_mode",
        return_value="temp_proj",
    )

    result = manager.validate_project(
        jwk_path="a",
        sa_id="c",
        base_url="d",
    )

    assert result == "temp_proj"


def test_validate_project_onprem_argument_mode(mocker):
    config_store = mocker.Mock()
    token_manager = mocker.Mock()
    config_store.get_current_project.return_value = None

    mocker.patch.object(
        manager := AuthManager(config_store, token_manager),
        "_initialize_argument_mode_onprem",
        return_value="temp_proj",
    )

    result = manager.validate_project(
        auth_mode="onprem",
        base_url="url",
        onprem_username="u",
        onprem_password="p",
    )

    assert result == "temp_proj"


def test_cleanup_argument_mode_restores_original_project(mocker):
    config_store = mocker.Mock()
    token_manager = mocker.Mock()

    manager = AuthManager(config_store, token_manager)
    manager._temp_project = "temp_x"
    manager._original_project = "orig"

    manager.cleanup_argument_mode()

    config_store.set_current_project.assert_called_once_with("orig")


def test_update_config_if_needed_updates_fields(mocker):
    config_store = mocker.Mock()
    token_manager = mocker.Mock()

    config_store.get_current_project.return_value = "proj"
    config_store.get_project_config.return_value = {}

    manager = AuthManager(config_store, token_manager)

    manager.update_config_if_needed(
        jwk_path="a",
        sa_id="c",
        base_url="d",
    )

    config_store.save_project.assert_called_once()
    args = config_store.save_project.call_args[0]
    saved_config = args[1]

    assert saved_config["jwk_path"] == "a"
    assert saved_config["sa_id"] == "c"
    assert saved_config["base_url"] == "d"
    assert "token_url" in saved_config


def test_get_auth_mode_override(mocker):
    config_store = mocker.Mock()
    token_manager = mocker.Mock()

    manager = AuthManager(config_store, token_manager)
    result = manager.get_auth_mode("proj", override="onprem")

    assert result == "onprem"


def test_get_auth_mode_from_config(mocker):
    config_store = mocker.Mock()
    token_manager = mocker.Mock()

    config_store.get_project_config.return_value = {"auth_mode": "onprem"}

    manager = AuthManager(config_store, token_manager)
    result = manager.get_auth_mode("proj")

    assert result == "onprem"


def test_get_token_success(mocker):
    config_store = mocker.Mock()
    token_manager = mocker.Mock()
    token_manager.get_token.return_value = "token123"

    manager = AuthManager(config_store, token_manager)
    result = manager.get_token("proj")

    assert result == "token123"


def test_get_token_failure_raises_exit(mocker):
    config_store = mocker.Mock()
    token_manager = mocker.Mock()
    token_manager.get_token.side_effect = Exception("fail")

    manager = AuthManager(config_store, token_manager)

    with pytest.raises(typer.Exit):
        manager.get_token("proj")


def test_get_onprem_session_success(mocker):
    config_store = mocker.Mock()
    token_manager = mocker.Mock()

    config_store.get_project_config.return_value = {
        "base_url": "url",
        "onprem_username": "u",
        "onprem_realm": "root",
    }

    mock_client = mocker.Mock()
    mock_client.authenticate.return_value = {"tokenId": "sso"}

    mocker.patch(
        "trxo.commands.shared.auth_manager.OnPremAuth", return_value=mock_client
    )

    manager = AuthManager(config_store, token_manager)
    result = manager.get_onprem_session("proj", password="p")

    assert result == "sso"


def test_get_onprem_session_failure_raises_exit(mocker):
    config_store = mocker.Mock()
    token_manager = mocker.Mock()

    config_store.get_project_config.return_value = {"base_url": "url"}

    mock_client = mocker.Mock()
    mock_client.authenticate.side_effect = Exception("fail")

    mocker.patch(
        "trxo.commands.shared.auth_manager.OnPremAuth", return_value=mock_client
    )

    manager = AuthManager(config_store, token_manager)

    with pytest.raises(typer.Exit):
        manager.get_onprem_session("proj", username="u", password="p")


def test_get_base_url_override(mocker):
    config_store = mocker.Mock()
    token_manager = mocker.Mock()

    manager = AuthManager(config_store, token_manager)
    result = manager.get_base_url("proj", base_url_override="x")

    assert result == "x"


def test_get_base_url_missing_raises_exit(mocker):
    config_store = mocker.Mock()
    token_manager = mocker.Mock()
    config_store.get_project_config.return_value = {}

    manager = AuthManager(config_store, token_manager)

    with pytest.raises(typer.Exit):
        manager.get_base_url("proj")


# ─── IDM/on-prem additions ──────────────────────────────────────────────────


def test_validate_project_onprem_idm_argument_mode(mocker):
    """am_base_url + idm_username/idm_password should trigger onprem argument mode."""
    config_store = mocker.Mock()
    token_manager = mocker.Mock()
    config_store.get_current_project.return_value = None

    mocker.patch.object(
        manager := AuthManager(config_store, token_manager),
        "_initialize_argument_mode_onprem",
        return_value="temp_idm",
    )

    result = manager.validate_project(
        auth_mode="onprem",
        base_url="http://am",
        am_base_url="http://am",
        idm_username="idm_user",
        idm_password="idm_pass",
    )

    assert result == "temp_idm"


def test_initialize_argument_mode_onprem_stores_am_base_url(mocker):
    """Ensure am_base_url is persisted inside the temporary project config."""
    config_store = mocker.Mock()
    config_store.get_current_project.return_value = None
    token_manager = mocker.Mock()

    manager = AuthManager(config_store, token_manager)

    result = manager._initialize_argument_mode_onprem(
        base_url="http://am",
        username="amAdmin",
        am_base_url="http://am",
    )

    assert result is not None
    saved = config_store.save_project.call_args[0][1]
    assert saved.get("am_base_url") == "http://am"
    assert saved.get("auth_mode") == "onprem"


def test_get_base_url_falls_back_to_am_base_url(mocker):
    """get_base_url should prefer am_base_url config field over base_url."""
    config_store = mocker.Mock()
    token_manager = mocker.Mock()
    config_store.get_project_config.return_value = {
        "am_base_url": "http://am",
        "base_url": "http://old",
    }

    manager = AuthManager(config_store, token_manager)
    result = manager.get_base_url("proj")

    assert result == "http://am"


def test_get_idm_credentials_success(mocker):
    config_store = mocker.Mock()
    token_manager = mocker.Mock()
    config_store.get_project_config.return_value = {
        "onprem_products": ["idm"],
        "idm_username": "idmAdmin",
    }

    manager = AuthManager(config_store, token_manager)
    username, password = manager.get_idm_credentials("proj", idm_password="secret")

    assert username == "idmAdmin"
    assert password == "secret"


def test_get_idm_credentials_missing_products_raises(mocker):
    config_store = mocker.Mock()
    token_manager = mocker.Mock()
    config_store.get_project_config.return_value = {"onprem_products": []}

    manager = AuthManager(config_store, token_manager)

    with pytest.raises(typer.Exit):
        manager.get_idm_credentials("proj", idm_password="pw")


def test_get_idm_base_url_from_override(mocker):
    config_store = mocker.Mock()
    token_manager = mocker.Mock()

    manager = AuthManager(config_store, token_manager)
    result = manager.get_idm_base_url("proj", idm_base_url_override="http://idm")

    assert result == "http://idm"


def test_get_idm_base_url_from_config(mocker):
    config_store = mocker.Mock()
    token_manager = mocker.Mock()
    config_store.get_project_config.return_value = {"idm_base_url": "http://idm-config"}

    manager = AuthManager(config_store, token_manager)
    result = manager.get_idm_base_url("proj")

    assert result == "http://idm-config"


def test_get_idm_base_url_missing_raises(mocker):
    config_store = mocker.Mock()
    token_manager = mocker.Mock()
    config_store.get_project_config.return_value = {}

    manager = AuthManager(config_store, token_manager)

    with pytest.raises(typer.Exit):
        manager.get_idm_base_url("proj")
