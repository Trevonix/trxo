"""Unit tests for trxo.utils.diff_presenter (DiffPresenter)."""

from unittest.mock import MagicMock

import pytest

from trxo_lib.state.diff.diff_engine import ChangeType, DiffResult
from trxo.utils.diff_presenter import DiffPresenter


class FakeItem:
    def __init__(self, item_id, name, change_type, summary="ok", detailed_changes=None):
        self.item_id = item_id
        self.item_name = name
        self.change_type = change_type
        self.summary = summary
        self.changes_count = 1
        self.detailed_changes = detailed_changes or {}

    def get_unified_diff(self):
        return ""


def make_diff_result(
    cmd="x",
    realm=None,
    added=None,
    modified=None,
    removed=None,
    unchanged=None,
    insights=None,
):
    return DiffResult(
        command_name=cmd,
        realm=realm,
        total_items_current=1,
        total_items_new=2,
        added_items=added or [],
        modified_items=modified or [],
        removed_items=removed or [],
        unchanged_items=unchanged or [],
        raw_diff={},
        key_insights=insights or [],
    )


def test_display_diff_summary_no_changes(mocker):
    presenter = DiffPresenter()
    mocker.patch.object(presenter, "console")
    dr = make_diff_result()
    presenter.display_diff_summary(dr)


def test_display_diff_summary_with_changes(mocker):
    presenter = DiffPresenter()
    mocker.patch.object(presenter, "console")

    added = [FakeItem("1", "a", ChangeType.ADDED)]
    dr = make_diff_result(added=added, insights=["hello"])
    presenter.display_diff_summary(dr)


def test_display_diff_summary_exception(mocker):
    presenter = DiffPresenter()
    mocker.patch.object(presenter, "console", side_effect=Exception("boom"))
    mocker.patch("trxo.utils.diff_presenter.error")

    dr = make_diff_result()
    presenter.display_diff_summary(dr)


def test_display_changes_table(mocker):
    presenter = DiffPresenter()
    mocker.patch.object(presenter, "console")

    items = [
        FakeItem("1", "a", ChangeType.ADDED),
        FakeItem("2", "b", ChangeType.MODIFIED),
        FakeItem("3", "c", ChangeType.REMOVED),
    ]

    dr = make_diff_result(
        added=[items[0]],
        modified=[items[1]],
        removed=[items[2]],
    )

    presenter.display_diff_summary(dr)


def test_display_key_insights_non_oauth(mocker):
    presenter = DiffPresenter()
    mocker.patch.object(presenter, "console")

    dr = make_diff_result(cmd="services", insights=["x", "y"])
    presenter._display_key_insights(dr.key_insights, dr)


def test_display_key_insights_oauth(mocker):
    presenter = DiffPresenter()
    mocker.patch.object(presenter, "console")

    insights = [
        "grantTypes: c1, c2",
        "scopes: c3",
    ]

    mod = [FakeItem("1", "a", ChangeType.MODIFIED)]
    dr = make_diff_result(cmd="oauth", modified=mod, insights=insights)

    presenter._display_key_insights(dr.key_insights, dr)


def test_generate_html_report_success(tmp_path, mocker):
    presenter = DiffPresenter()
    mocker.patch("trxo.utils.diff_presenter.info")

    dr = make_diff_result(cmd="x")
    path = presenter.generate_html_report(dr, {"a": 1}, {"a": 2}, output_dir=str(tmp_path))

    from pathlib import Path
    assert Path(path).exists()


def test_generate_html_report_failure(mocker):
    presenter = DiffPresenter()
    mocker.patch("trxo.utils.diff_presenter.error")

    mocker.patch("pathlib.Path.mkdir", side_effect=Exception("boom"))

    dr = make_diff_result(cmd="x")
    out = presenter.generate_html_report(dr, {}, {}, output_dir="bad")
    assert out is None


def test_generate_html_content_branches():
    presenter = DiffPresenter()

    mod = [FakeItem("1", "a", ChangeType.MODIFIED)]
    dr = make_diff_result(cmd="x", modified=mod)

    html = presenter._generate_html_content(dr)
    assert "Diff Report" in html


def test_generate_stats_html():
    presenter = DiffPresenter()
    dr = make_diff_result(
        added=[FakeItem("1", "a", ChangeType.ADDED)],
        modified=[FakeItem("2", "b", ChangeType.MODIFIED)],
        removed=[FakeItem("3", "c", ChangeType.REMOVED)],
    )

    html = presenter._generate_stats_html(dr)
    assert "Current Items" in html
    assert "Added" in html


def test_generate_changes_html_no_changes():
    presenter = DiffPresenter()
    dr = make_diff_result()
    html = presenter._generate_changes_html(dr)
    assert "No Changes" in html


def test_generate_changes_html_with_changes():
    presenter = DiffPresenter()
    dr = make_diff_result(
        added=[FakeItem("1", "a", ChangeType.ADDED)],
        modified=[FakeItem("2", "b", ChangeType.MODIFIED)],
    )

    html = presenter._generate_changes_html(dr)
    assert "Changes Detail" in html or "change-added" in html


def test_generate_insights_html_non_oauth():
    presenter = DiffPresenter()
    dr = make_diff_result(cmd="services", insights=["  • x", "    - y"])
    html = presenter._generate_insights_html(dr)
    assert "Key Insights" in html


def test_generate_insights_html_oauth():
    presenter = DiffPresenter()

    insights = ["grantTypes: c1, c2"]
    dr = make_diff_result(
        cmd="oauth",
        modified=[FakeItem("1", "a", ChangeType.MODIFIED)],
        insights=insights,
    )

    html = presenter._generate_insights_html(dr)
    assert "oauth" in html.lower() or "grantTypes" in html
