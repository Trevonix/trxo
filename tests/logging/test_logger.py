import logging
import pytest

from trxo.logging import (
    setup_logging,
    get_logger,
    log_api_call,
    log_transaction,
    log_application_event,
    log_authentication_event,
)


def _fake_file_handler(*args, **kwargs):
    handler = logging.NullHandler()
    handler.setLevel(logging.DEBUG)
    return handler


def _fake_stream_handler(*args, **kwargs):
    handler = logging.NullHandler()
    handler.setLevel(logging.WARNING)
    return handler


def test_setup_logging_basic(mocker, tmp_path):
    mocker.patch(
        "trxo.logging.config.get_log_file_path",
        return_value=tmp_path / "trxo.log",
    )
    mocker.patch(
        "logging.handlers.TimedRotatingFileHandler", side_effect=_fake_file_handler
    )
    mocker.patch("logging.StreamHandler", side_effect=_fake_stream_handler)

    setup_logging(force_reconfigure=True)

    root_logger = logging.getLogger("trxo")
    assert root_logger.handlers


def test_get_logger_returns_same_instance(mocker, tmp_path):
    mocker.patch(
        "trxo.logging.config.get_log_file_path",
        return_value=tmp_path / "trxo.log",
    )
    mocker.patch(
        "logging.handlers.TimedRotatingFileHandler", side_effect=_fake_file_handler
    )
    mocker.patch("logging.StreamHandler", side_effect=_fake_stream_handler)

    setup_logging(force_reconfigure=True)

    logger1 = get_logger("trxo.test")
    logger2 = get_logger("trxo.test")

    assert logger1 is logger2


def test_log_api_call_success(mocker):
    real_logger = logging.getLogger("trxo.api")
    spy = mocker.spy(real_logger, "debug")

    log_api_call("GET", "/test", status_code=200, duration=0.1)

    spy.assert_called_once()


def test_log_api_call_client_error(mocker):
    real_logger = logging.getLogger("trxo.api")
    spy = mocker.spy(real_logger, "warning")

    log_api_call("POST", "/bad", status_code=404, duration=0.2)

    spy.assert_called_once()


def test_log_api_call_server_error(mocker):
    real_logger = logging.getLogger("trxo.api")
    spy = mocker.spy(real_logger, "error")

    log_api_call("POST", "/crash", status_code=500, duration=0.2, error="boom")

    spy.assert_called_once()


def test_log_transaction_sanitizes_details(mocker):
    mocker.patch("trxo.logging.utils.sanitize_data", return_value={"token": "***"})

    real_logger = logging.getLogger("trxo.transaction")
    spy = mocker.spy(real_logger, "debug")

    log_transaction("export", {"token": "secret"})

    spy.assert_called_once()
    _, kwargs = spy.call_args
    assert kwargs["extra"]["transaction_details"]["token"] == "***"


def test_log_application_event_info(mocker):
    real_logger = logging.getLogger("trxo.app")
    spy = mocker.spy(real_logger, "info")

    log_application_event("startup", level="info")

    spy.assert_called_once()


def test_log_application_event_custom_level(mocker):
    real_logger = logging.getLogger("trxo.app")
    spy = mocker.spy(real_logger, "error")

    log_application_event("bad", level="error")

    spy.assert_called_once()


def test_log_authentication_event_success(mocker):
    real_logger = logging.getLogger("trxo.auth")
    spy = mocker.spy(real_logger, "info")

    log_authentication_event("service-account", True)

    spy.assert_called_once()


def test_log_authentication_event_failure(mocker):
    real_logger = logging.getLogger("trxo.auth")
    spy = mocker.spy(real_logger, "error")

    log_authentication_event("onprem", False)

    spy.assert_called_once()
