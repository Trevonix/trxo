import json
import pytest
import typer
import httpx

from trxo.commands.shared.base_command import BaseCommand


class DummyCommand(BaseCommand):
    def get_required_fields(self):
        return ["id"]

    def get_item_type(self):
        return "items"


def test_initialize_auth_service_account(mocker):
    cmd = DummyCommand()

    mocker.patch.object(cmd.auth_manager, "validate_project", return_value="proj")
    mocker.patch.object(cmd.auth_manager, "update_config_if_needed")
    mocker.patch.object(
        cmd.auth_manager, "get_auth_mode", return_value="service-account"
    )
    mocker.patch.object(cmd.auth_manager, "get_base_url", return_value="http://x")
    mocker.patch.object(cmd.auth_manager, "get_token", return_value="token")

    token, base_url = cmd.initialize_auth(
        jwk_path="a",
        sa_id="c",
        base_url="http://x",
    )

    assert token == "token"
    assert base_url == "http://x"
    assert cmd.auth_mode == "service-account"


def test_initialize_auth_onprem(mocker):
    cmd = DummyCommand()

    mocker.patch.object(cmd.auth_manager, "validate_project", return_value="proj")
    mocker.patch.object(cmd.auth_manager, "update_config_if_needed")
    mocker.patch.object(cmd.auth_manager, "get_auth_mode", return_value="onprem")
    mocker.patch.object(cmd.auth_manager, "get_base_url", return_value="http://x")
    mocker.patch.object(cmd.auth_manager, "get_onprem_session", return_value="sso")

    token, base_url = cmd.initialize_auth(
        auth_mode="onprem",
        base_url="http://x",
        onprem_username="u",
        onprem_password="p",
    )

    assert token == "sso"
    assert base_url == "http://x"
    assert cmd.auth_mode == "onprem"


def test_initialize_auth_onprem_with_am_base_url(mocker):
    """am_base_url is forwarded to validate_project so auth is performed against AM."""
    cmd = DummyCommand()

    validate = mocker.patch.object(
        cmd.auth_manager, "validate_project", return_value="proj"
    )
    mocker.patch.object(cmd.auth_manager, "update_config_if_needed")
    mocker.patch.object(cmd.auth_manager, "get_auth_mode", return_value="onprem")
    mocker.patch.object(cmd.auth_manager, "get_base_url", return_value="http://am")
    mocker.patch.object(cmd.auth_manager, "get_onprem_session", return_value="sso")

    cmd.initialize_auth(
        auth_mode="onprem",
        base_url="http://am",
        am_base_url="http://am",
        onprem_username="u",
        onprem_password="p",
    )

    call_kwargs = validate.call_args.kwargs
    assert call_kwargs.get("am_base_url") == "http://am"


def test_build_auth_headers_service_account():
    cmd = DummyCommand()
    cmd.auth_mode = "service-account"

    headers = cmd.build_auth_headers("token")
    assert headers["Authorization"] == "Bearer token"


def test_build_auth_headers_onprem():
    cmd = DummyCommand()
    cmd.auth_mode = "onprem"

    headers = cmd.build_auth_headers("sso")
    assert headers["Cookie"] == "iPlanetDirectoryPro=sso"


def test_make_http_request_success(mocker):
    cmd = DummyCommand()

    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.content = b"ok"
    mock_response.headers = {}
    mock_response.raise_for_status.return_value = None

    mock_client = mocker.Mock()
    mock_client.get.return_value = mock_response

    mocker.patch(
        "httpx.Client",
        return_value=mocker.Mock(
            __enter__=lambda s: mock_client, __exit__=lambda *a: None
        ),
    )
    mocker.patch("trxo.commands.shared.base_command.log_api_call")

    response = cmd.make_http_request("http://x")

    assert response == mock_response


def test_make_http_request_http_error(mocker):
    cmd = DummyCommand()

    response = mocker.Mock()
    response.status_code = 400
    response.text = "bad"
    response.content = b"bad"
    response.headers = {}
    response.json.side_effect = Exception()

    http_error = httpx.HTTPStatusError(
        "err",
        request=mocker.Mock(),
        response=response,
    )

    mock_client = mocker.Mock()
    mock_client.get.side_effect = http_error

    mocker.patch(
        "httpx.Client",
        return_value=mocker.Mock(
            __enter__=lambda s: mock_client, __exit__=lambda *a: None
        ),
    )
    mocker.patch("trxo.commands.shared.base_command.log_api_call")

    with pytest.raises(Exception):
        cmd.make_http_request("http://x")


def test_print_summary_success():
    cmd = DummyCommand()
    cmd.successful_updates = 1
    cmd.failed_updates = 0

    cmd.print_summary()


def test_print_summary_failure_raises():
    cmd = DummyCommand()
    cmd.successful_updates = 0
    cmd.failed_updates = 1

    with pytest.raises(typer.Exit):
        cmd.print_summary()


def test_print_summary_no_success_raises():
    cmd = DummyCommand()
    cmd.successful_updates = 0
    cmd.failed_updates = 0

    with pytest.raises(typer.Exit):
        cmd.print_summary()
