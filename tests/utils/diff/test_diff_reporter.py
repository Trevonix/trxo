import pytest
from unittest.mock import MagicMock
from pathlib import Path

from trxo.utils.diff.diff_reporter import DiffReporter
from trxo.utils.diff.diff_engine import ChangeType


@pytest.fixture
def fake_diff_result():
    diff = MagicMock()

    diff.command_name = "journeys"
    diff.realm = "alpha"
    diff.total_items_current = 2
    diff.total_items_new = 3
    diff.key_insights = []

    added_item = MagicMock()
    added_item.change_type = ChangeType.ADDED
    added_item.item_id = "1"
    added_item.item_name = "item1"
    added_item.summary = "added item"
    added_item.detailed_changes = {}

    modified_item = MagicMock()
    modified_item.change_type = ChangeType.MODIFIED
    modified_item.item_id = "2"
    modified_item.item_name = "item2"
    modified_item.summary = "modified item"
    modified_item.detailed_changes = {
        "current_item": {"a": 1},
        "new_item": {"a": 2},
    }

    removed_item = MagicMock()
    removed_item.change_type = ChangeType.REMOVED
    removed_item.item_id = "3"
    removed_item.item_name = "item3"
    removed_item.summary = "removed item"
    removed_item.detailed_changes = {}

    diff.added_items = [added_item]
    diff.modified_items = [modified_item]
    diff.removed_items = [removed_item]
    diff.unchanged_items = []

    return diff


def test_display_summary_success(mocker, fake_diff_result):
    reporter = DiffReporter()

    # Patch console.print safely
    reporter.console.print = mocker.MagicMock()

    # No exceptions should be raised
    reporter.display_summary(fake_diff_result)

    assert reporter.console.print.called


def test_has_changes_true(fake_diff_result):
    reporter = DiffReporter()
    assert reporter._has_changes(fake_diff_result) is True


def test_has_changes_false(mocker):
    reporter = DiffReporter()

    diff = MagicMock()
    diff.added_items = []
    diff.modified_items = []
    diff.removed_items = []

    assert reporter._has_changes(diff) is False


def test_generate_html_diff_success(mocker, fake_diff_result, tmp_path):
    reporter = DiffReporter()

    mocker.patch("trxo.utils.diff.diff_reporter.info")
    mocker.patch("trxo.utils.diff.diff_reporter.success")

    mocker.patch.object(
        reporter,
        "_generate_html_content",
        return_value="<html><body>ok</body></html>",
    )

    current_data = {"a": 1}
    new_data = {"a": 2}

    html_path = reporter.generate_html_diff(
        diff_result=fake_diff_result,
        current_data=current_data,
        new_data=new_data,
        output_dir=str(tmp_path),
    )

    assert html_path is not None
    assert Path(html_path).exists()


def test_generate_html_diff_exception(mocker, fake_diff_result):
    reporter = DiffReporter()

    mocker.patch("trxo.utils.diff.diff_reporter.info")
    mocker.patch("trxo.utils.diff.diff_reporter.error")

    # Force exception by making mkdir fail
    mocker.patch("pathlib.Path.mkdir", side_effect=Exception("boom"))

    result = reporter.generate_html_diff(
        diff_result=fake_diff_result,
        current_data={},
        new_data={},
        output_dir="invalid_path",
    )

    assert result is None
