import pytest
from unittest.mock import MagicMock

from trxo.utils.diff.diff_manager import DiffManager


def test_perform_diff_success(mocker):
    manager = DiffManager()

    # Mock get_command_api_endpoint at correct import path
    mocker.patch(
        "trxo.utils.diff.diff_manager.get_command_api_endpoint",
        return_value=("/api/test", None),
    )

    # Mock DataFetcher methods
    manager.data_fetcher.fetch_data = mocker.MagicMock(return_value={"current": 1})
    manager.data_fetcher.fetch_from_file_or_git = mocker.MagicMock(
        return_value={"new": 2}
    )

    # Mock DiffEngine
    fake_diff_result = MagicMock()
    manager.diff_engine.compare_data = mocker.MagicMock(return_value=fake_diff_result)

    # Mock DiffReporter
    manager.diff_reporter.display_summary = mocker.MagicMock()
    manager.diff_reporter.generate_html_diff = mocker.MagicMock(
        return_value="/tmp/report.html"
    )

    result = manager.perform_diff(
        command_name="journeys",
        file_path="test.json",
        realm="alpha",
    )

    assert result == fake_diff_result

    manager.data_fetcher.fetch_data.assert_called_once()
    manager.data_fetcher.fetch_from_file_or_git.assert_called_once()
    manager.diff_engine.compare_data.assert_called_once()
    manager.diff_reporter.display_summary.assert_called_once()
    manager.diff_reporter.generate_html_diff.assert_called_once()


def test_perform_diff_fails_on_current_data_fetch(mocker):
    manager = DiffManager()

    mocker.patch(
        "trxo.utils.diff.diff_manager.get_command_api_endpoint",
        return_value=("/api/test", None),
    )

    manager.data_fetcher.fetch_data = mocker.MagicMock(return_value=None)

    result = manager.perform_diff(command_name="journeys")

    assert result is None


def test_perform_diff_fails_on_import_data_fetch(mocker):
    manager = DiffManager()

    mocker.patch(
        "trxo.utils.diff.diff_manager.get_command_api_endpoint",
        return_value=("/api/test", None),
    )

    manager.data_fetcher.fetch_data = mocker.MagicMock(return_value={"current": 1})
    manager.data_fetcher.fetch_from_file_or_git = mocker.MagicMock(return_value=None)

    result = manager.perform_diff(command_name="journeys")

    assert result is None


def test_quick_diff_success(mocker):
    manager = DiffManager()

    fake_diff_result = MagicMock()
    manager.diff_engine.compare_data = mocker.MagicMock(return_value=fake_diff_result)
    manager.diff_reporter.display_summary = mocker.MagicMock()

    result = manager.quick_diff(
        command_name="journeys",
        current_data={"a": 1},
        new_data={"a": 2},
        realm="alpha",
    )

    assert result == fake_diff_result
    manager.diff_engine.compare_data.assert_called_once()
    manager.diff_reporter.display_summary.assert_called_once()


def test_quick_diff_exception(mocker):
    manager = DiffManager()

    manager.diff_engine.compare_data = mocker.MagicMock(side_effect=Exception("Boom"))

    result = manager.quick_diff(
        command_name="journeys",
        current_data={"a": 1},
        new_data={"a": 2},
    )

    assert result is None
