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
        client_id="b",
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
        client_id="b",
        sa_id="c",
        base_url="d",
    )

    config_store.save_project.assert_called_once()
    args = config_store.save_project.call_args[0]
    saved_config = args[1]

    assert saved_config["jwk_path"] == "a"
    assert saved_config["client_id"] == "b"
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
