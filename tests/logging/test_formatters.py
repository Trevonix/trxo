import logging
import pytest
from trxo.logging.formatters import TRxOFormatter, APICallFormatter, MultiplexFormatter


def test_trxo_formatter_basic_format():
    formatter = TRxOFormatter(include_timestamps=False)
    record = logging.LogRecord(
        name="trxo.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="hello",
        args=(),
        exc_info=None,
    )

    output = formatter.format(record)
    assert "INFO" in output
    assert "[trxo.test]" in output
    assert "hello" in output


def test_trxo_formatter_sanitizes_msg(mocker):
    mocker.patch(
        "trxo.logging.formatters.sanitize_data",
        return_value={"token": "***"},
    )

    formatter = TRxOFormatter(include_timestamps=False)
    record = logging.LogRecord(
        name="trxo.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg={"token": "secret"},
        args=(),
        exc_info=None,
    )

    output = formatter.format(record)
    assert "***" in output


def test_trxo_formatter_sanitizes_args(mocker):
    mocker.patch(
        "trxo.logging.formatters.sanitize_data",
        return_value={"token": "***"},
    )

    formatter = TRxOFormatter(include_timestamps=False)
    record = logging.LogRecord(
        name="trxo.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg={"token": "secret"},
        args=(),
        exc_info=None,
    )

    output = formatter.format(record)
    assert "***" in output


def test_api_call_formatter_basic():
    formatter = APICallFormatter()
    record = logging.LogRecord(
        name="trxo.api",
        level=logging.DEBUG,
        pathname=__file__,
        lineno=10,
        msg="",
        args=(),
        exc_info=None,
    )

    record.api_method = "GET"
    record.api_url = "/test"
    record.api_status = 200
    record.api_duration = 0.123

    output = formatter.format(record)
    assert "GET /test" in output
    assert "200" in output
    assert "ms" in output


def test_multiplex_formatter_uses_api_formatter():
    default_formatter = TRxOFormatter(include_timestamps=False)
    api_formatter = APICallFormatter()
    formatter = MultiplexFormatter(default_formatter, api_formatter)

    record = logging.LogRecord(
        name="trxo.api",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="",
        args=(),
        exc_info=None,
    )

    record.api_method = "POST"
    record.api_url = "/login"
    record.api_status = 401
    record.api_duration = 0.5

    output = formatter.format(record)
    assert "POST /login" in output
    assert "401" in output


def test_multiplex_formatter_uses_default_formatter():
    default_formatter = TRxOFormatter(include_timestamps=False)
    api_formatter = APICallFormatter()
    formatter = MultiplexFormatter(default_formatter, api_formatter)

    record = logging.LogRecord(
        name="trxo.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=10,
        msg="warning message",
        args=(),
        exc_info=None,
    )

    output = formatter.format(record)
    assert "WARNING" in output
    assert "warning message" in output
