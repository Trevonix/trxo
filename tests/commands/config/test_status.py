import pytest

from trxo.commands.config.status import StatusChecker
from trxo.utils.config_store import ConfigStore


def test_status_checker_detects_git_mode_and_both_auth_modes():
    config = {
        "storage_mode": "git",
        "am_base_url": "https://am.example.com",
        "idm_base_url": "https://idm.example.com",
    }

    checker = StatusChecker(project_name="test_project", config=config, no_prompt=True)
    checker.detect_auth_mode()

    assert checker.auth_mode == ["am", "idm"]
    assert checker.total_checks == 1
    assert checker.successful_checks == 1
    assert checker.results[0].name == "Auth mode detected"
    assert checker.results[0].success is True


def test_status_checker_detects_aic_auth_mode():
    config = {
        "storage_mode": "git",
        "base_url": "https://alpha.id.pingidentity.com",
    }

    checker = StatusChecker(project_name="test_project", config=config, no_prompt=True)
    checker.detect_auth_mode()

    assert checker.auth_mode == ["aic"]
    assert checker.total_checks == 1
    assert checker.successful_checks == 1
    assert checker.results[0].name == "Auth mode detected"
    assert checker.results[0].success is True


def test_git_validation_reports_missing_credentials(mocker):
    config = {"storage_mode": "git"}
    checker = StatusChecker(project_name="test_project", config=config, no_prompt=True)

    mocker.patch.object(ConfigStore, "get_git_credentials", return_value=None)

    checker.git_validation()

    assert checker.total_checks == 1
    assert checker.successful_checks == 0
    assert checker.results[0].name == "Git token valid"
    assert checker.results[0].success is False


def test_git_validation_uses_validate_credentials(mocker):
    config = {"storage_mode": "git"}
    checker = StatusChecker(project_name="test_project", config=config, no_prompt=True)

    mocker.patch.object(
        ConfigStore,
        "get_git_credentials",
        return_value={"token": "abc123", "repo_url": "https://github.com/test/repo"},
    )
    mocker.patch("trxo.commands.config.status.validate_credentials", return_value={})

    checker.git_validation()

    assert checker.total_checks == 1
    assert checker.successful_checks == 1
    assert checker.results[0].name == "Git token valid"
    assert checker.results[0].success is True


def test_idm_access_uses_explicit_idm_credentials_when_provided(mocker):
    config = {
        "am_base_url": "http://localhost:8081",
        "idm_base_url": "http://localhost:8080",
        "idm_username": "idm-admin",
        "idm_password": "idm-pass",
    }
    checker = StatusChecker(project_name="test_project", config=config, no_prompt=True)
    checker.auth_mode_config = "onprem"
    checker.am_token = "am-token"

    checker.detect_auth_mode()  # Ensure idm_url is set

    mock_response = mocker.Mock()
    mock_response.raise_for_status = mocker.Mock()
    mock_response.status_code = 200

    mock_client = mocker.Mock()
    mock_client.get.return_value = mock_response

    mock_client_class = mocker.patch("trxo.commands.config.status.httpx.Client")
    mock_client_class.return_value.__enter__.return_value = mock_client
    mock_client_class.return_value.__exit__.return_value = None

    checker.check_idm_access()

    expected_endpoint = "http://localhost:8080/openidm/info/ping"
    mock_client.get.assert_called_once_with(
        expected_endpoint,
        headers={
            "X-OpenIDM-Username": "idm-admin",
            "X-OpenIDM-Password": "idm-pass",
            "Content-Type": "application/json",
        },
    )
    assert checker.results[-1].success is True
    assert checker.results[-1].name == "IDM access successful"
