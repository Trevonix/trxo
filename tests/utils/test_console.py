import pytest
from unittest.mock import MagicMock

import trxo.utils.console as console_utils


def test_success_prints(mocker):
    mock_print = mocker.patch.object(console_utils.console, "print")
    console_utils.success("ok")
    mock_print.assert_called_once()


def test_error_prints(mocker):
    mock_print = mocker.patch.object(console_utils.console, "print")
    console_utils.error("fail")
    mock_print.assert_called_once()


def test_warning_prints(mocker):
    mock_print = mocker.patch.object(console_utils.console, "print")
    console_utils.warning("warn")
    mock_print.assert_called_once()


def test_info_prints(mocker):
    mock_print = mocker.patch.object(console_utils.console, "print")
    console_utils.info("hello")
    mock_print.assert_called_once()


def test_create_table():
    table = console_utils.create_table("Title", ["a", "b"])
    assert table.title == "Title"
    assert len(table.columns) == 2


def test_display_panel(mocker):
    mock_print = mocker.patch.object(console_utils.console, "print")
    console_utils.display_panel("content", "title")
    mock_print.assert_called_once()
