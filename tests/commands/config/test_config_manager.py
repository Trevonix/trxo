import json
import pytest
import typer

from trxo.commands.config.config_manager import (
    setup,
    show,
    set_log_level,
    get_log_level,
)


@pytest.fixture
def mock_config_store(mocker, tmp_path):
    store = mocker.Mock()
    store.base_dir = tmp_path
    store.get_current_project.return_value = "proj"
    store.get_project_config.return_value = {}
    mocker.patch("trxo.commands.config.config_manager.config_store", store)
    return store


@pytest.fixture
def base_setup_mocks(mocker):
    mocker.patch(
        "trxo.commands.config.config_manager.get_credential_value",
        side_effect=lambda v, *_args, **_kwargs: v,
    )
    mocker.patch(
        "trxo.commands.config.config_manager.setup_service_account_auth",
        return_value={"auth_mode": "service-account"},
    )
    mocker.patch(
        "trxo.commands.config.config_manager.setup_onprem_auth",
        return_value={"auth_mode": "onprem"},
    )
    mocker.patch("trxo.commands.config.config_manager.success")
    mocker.patch("trxo.commands.config.config_manager.info")
    mocker.patch("trxo.commands.config.config_manager.warning")
    mocker.patch("trxo.commands.config.config_manager.error")
    return mocker


def test_setup_success_service_account(mock_config_store, base_setup_mocks):
    setup(
        jwk_path="jwk.json",
        sa_id="sid",
        base_url="https://example.com",
        am_base_url=None,
        auth_mode="service-account",
        onprem_username=None,
        onprem_realm="root",
        idm_base_url=None,
        idm_username=None,
        regions=None,
        storage_mode=None,
        git_username=None,
        git_repo=None,
        git_token=None,
    )

    mock_config_store.save_project.assert_called_once()
    project, config = mock_config_store.save_project.call_args.args
    assert project == "proj"
    assert config["auth_mode"] == "service-account"


def test_setup_success_onprem(mock_config_store, base_setup_mocks):
    setup(
        jwk_path=None,
        sa_id=None,
        base_url="https://example.com",
        am_base_url="http://am",
        auth_mode="onprem",
        onprem_username="user",
        onprem_realm="root",
        idm_base_url=None,
        idm_username=None,
        regions=None,
        storage_mode=None,
        git_username=None,
        git_repo=None,
        git_token=None,
    )

    mock_config_store.save_project.assert_called_once()
    _, config = mock_config_store.save_project.call_args.args
    assert config["auth_mode"] == "onprem"


def test_setup_no_active_project(mocker):
    store = mocker.Mock()
    store.get_current_project.return_value = None
    mocker.patch("trxo.commands.config.config_manager.config_store", store)
    mocker.patch("trxo.commands.config.config_manager.error")

    with pytest.raises(typer.Exit):
        setup(
            jwk_path=None,
            sa_id=None,
            base_url=None,
            am_base_url=None,
            auth_mode="service-account",
            onprem_username=None,
            onprem_realm="root",
            idm_base_url=None,
            idm_username=None,
            regions=None,
            storage_mode=None,
            git_username=None,
            git_repo=None,
            git_token=None,
        )


def test_setup_invalid_auth_mode(mock_config_store, base_setup_mocks):
    with pytest.raises(typer.Exit):
        setup(
            jwk_path="jwk.json",
            sa_id="sid",
            base_url="https://example.com",
            am_base_url=None,
            auth_mode="invalid",
            onprem_username=None,
            onprem_realm="root",
            idm_base_url=None,
            idm_username=None,
            regions=None,
            storage_mode=None,
            git_username=None,
            git_repo=None,
            git_token=None,
        )


def test_setup_existing_config_without_overrides_exits(
    mock_config_store, base_setup_mocks
):
    mock_config_store.get_project_config.return_value = {"base_url": "https://old.com"}

    with pytest.raises(typer.Exit):
        setup(
            jwk_path=None,
            sa_id=None,
            base_url=None,
            am_base_url=None,
            auth_mode="service-account",
            onprem_username=None,
            onprem_realm="root",
            idm_base_url=None,
            idm_username=None,
            regions=None,
            storage_mode=None,
            git_username=None,
            git_repo=None,
            git_token=None,
        )


def test_setup_existing_config_with_override_continues(
    mock_config_store, base_setup_mocks
):
    mock_config_store.get_project_config.return_value = {"base_url": "https://old.com"}

    setup(
        jwk_path=None,
        sa_id=None,
        base_url="https://new.com",
        am_base_url=None,
        auth_mode="service-account",
        onprem_username=None,
        onprem_realm="root",
        idm_base_url=None,
        idm_username=None,
        regions=None,
        storage_mode=None,
        git_username=None,
        git_repo=None,
        git_token=None,
    )

    mock_config_store.save_project.assert_called_once()


def test_show_success(mock_config_store, mocker):
    mocker.patch("trxo.commands.config.config_manager.display_config")
    show()
    mock_config_store.get_project_config.assert_called_once_with("proj")


def test_show_no_active_project(mocker):
    store = mocker.Mock()
    store.get_current_project.return_value = None
    mocker.patch("trxo.commands.config.config_manager.config_store", store)
    mocker.patch("trxo.commands.config.config_manager.error")

    with pytest.raises(typer.Exit):
        show()


def test_set_log_level_success(mock_config_store, mocker, tmp_path):
    mocker.patch("trxo.commands.config.config_manager.setup_logging")
    mocker.patch("trxo.commands.config.config_manager.get_logger")
    mocker.patch("trxo.commands.config.config_manager.success")
    mocker.patch("trxo.commands.config.config_manager.info")

    set_log_level("INFO")

    settings_file = tmp_path / "settings.json"
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert data["log_level"] == "INFO"


def test_set_log_level_invalid_level(mock_config_store, mocker):
    mocker.patch("trxo.commands.config.config_manager.setup_logging")
    mocker.patch("trxo.commands.config.config_manager.get_logger")
    mocker.patch("trxo.commands.config.config_manager.error")

    with pytest.raises(typer.Exit):
        set_log_level("BAD")


def test_set_log_level_existing_file_updated(mock_config_store, mocker, tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({"log_level": "DEBUG"}), encoding="utf-8")

    mocker.patch("trxo.commands.config.config_manager.setup_logging")
    mocker.patch("trxo.commands.config.config_manager.get_logger")
    mocker.patch("trxo.commands.config.config_manager.success")
    mocker.patch("trxo.commands.config.config_manager.info")

    set_log_level("ERROR")

    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert data["log_level"] == "ERROR"


def test_set_log_level_corrupt_file_recovers(mock_config_store, mocker, tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{bad json", encoding="utf-8")

    mocker.patch("trxo.commands.config.config_manager.setup_logging")
    mocker.patch("trxo.commands.config.config_manager.get_logger")
    mocker.patch("trxo.commands.config.config_manager.success")
    mocker.patch("trxo.commands.config.config_manager.info")

    set_log_level("WARNING")

    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert data["log_level"] == "WARNING"


def test_get_log_level_default(mock_config_store, mocker):
    mocker.patch("trxo.commands.config.config_manager.setup_logging")
    mocker.patch("trxo.commands.config.config_manager.get_logger")
    info_mock = mocker.patch("trxo.commands.config.config_manager.info")

    get_log_level()

    info_mock.assert_called_with("Current log level: INFO")


def test_get_log_level_from_file(mock_config_store, mocker, tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({"log_level": "DEBUG"}), encoding="utf-8")

    mocker.patch("trxo.commands.config.config_manager.setup_logging")
    mocker.patch("trxo.commands.config.config_manager.get_logger")
    info_mock = mocker.patch("trxo.commands.config.config_manager.info")

    get_log_level()

    info_mock.assert_called_with("Current log level: DEBUG")


def test_get_log_level_corrupt_file_defaults(mock_config_store, mocker, tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{bad json", encoding="utf-8")

    mocker.patch("trxo.commands.config.config_manager.setup_logging")
    mocker.patch("trxo.commands.config.config_manager.get_logger")
    info_mock = mocker.patch("trxo.commands.config.config_manager.info")

    get_log_level()

    info_mock.assert_called_with("Current log level: INFO")
