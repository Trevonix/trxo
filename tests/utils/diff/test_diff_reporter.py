import pytest
from pathlib import Path
from trxo.utils.diff.diff_reporter import DiffReporter
from trxo.utils.diff.diff_engine import DiffResult, ChangeType


class FakeItem:
    def __init__(self, item_id, name, change_type, summary="ok", detailed_changes=None):
        self.item_id = item_id
        self.item_name = name
        self.change_type = change_type
        self.summary = summary
        self.changes_count = 1
        self.detailed_changes = detailed_changes or {}


def make_diff_result(cmd="x", realm=None, added=None, modified=None, removed=None, unchanged=None, insights=None):
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


def test_display_summary_no_changes(mocker):
    rep = DiffReporter()
    mocker.patch.object(rep, "console")
    dr = make_diff_result()
    rep.display_summary(dr)


def test_display_summary_with_changes_and_insights(mocker):
    rep = DiffReporter()
    mocker.patch.object(rep, "console")

    added = [FakeItem("1", "a", ChangeType.ADDED)]
    dr = make_diff_result(added=added, insights=["hello"])

    mocker.patch.object(rep, "_display_key_insights")
    mocker.patch.object(rep, "_display_changes_table")

    rep.display_summary(dr)


def test_display_summary_exception(mocker):
    rep = DiffReporter()
    mocker.patch.object(rep, "console", side_effect=Exception("boom"))
    mocker.patch("trxo.utils.diff.diff_reporter.error")

    dr = make_diff_result()
    rep.display_summary(dr)


def test_display_changes_table(mocker):
    rep = DiffReporter()
    mocker.patch.object(rep, "console")

    items = [
        FakeItem("1", "a", ChangeType.ADDED),
        FakeItem("2", "b", ChangeType.MODIFIED),
        FakeItem("3", "c", ChangeType.REMOVED),
    ]
    dr = make_diff_result(added=[items[0]], modified=[items[1]], removed=[items[2]])

    rep._display_changes_table(dr)


def test_display_key_insights_non_oauth(mocker):
    rep = DiffReporter()
    mocker.patch.object(rep, "console")

    dr = make_diff_result(cmd="services", insights=["x", "y"])
    rep._display_key_insights(dr.key_insights, dr)


def test_display_key_insights_oauth(mocker):
    rep = DiffReporter()
    mocker.patch.object(rep, "console")

    insights = [
        "grantTypes: c1, c2",
        "scopes: c3",
    ]

    mod = [FakeItem("1", "a", ChangeType.MODIFIED)]
    dr = make_diff_result(cmd="oauth", modified=mod, insights=insights)

    rep._display_key_insights(dr.key_insights, dr)


def test_has_changes_true_and_false():
    rep = DiffReporter()
    dr1 = make_diff_result()
    dr2 = make_diff_result(added=[FakeItem("1", "a", ChangeType.ADDED)])

    assert rep._has_changes(dr1) is False
    assert rep._has_changes(dr2) is True


def test_generate_html_diff_success(tmp_path, mocker):
    rep = DiffReporter()
    mocker.patch("trxo.utils.diff.diff_reporter.success")

    dr = make_diff_result(cmd="x")
    path = rep.generate_html_diff(dr, {"a": 1}, {"a": 2}, output_dir=str(tmp_path))

    assert Path(path).exists()


def test_generate_html_diff_failure(mocker):
    rep = DiffReporter()
    mocker.patch("trxo.utils.diff.diff_reporter.info")
    mocker.patch("trxo.utils.diff.diff_reporter.error")

    mocker.patch("pathlib.Path.mkdir", side_effect=Exception("boom"))

    dr = make_diff_result(cmd="x")
    out = rep.generate_html_diff(dr, {}, {}, output_dir="bad")
    assert out is None


def test_generate_html_content_branches():
    rep = DiffReporter()

    detailed = {
        "current_item": {"a": 1},
        "new_item": {"a": 2},
        "reduced_current": {"a": 1},
        "reduced_new": {"a": 2},
    }

    mod = [FakeItem("1", "a", ChangeType.MODIFIED, detailed_changes=detailed)]
    dr = make_diff_result(cmd="x", modified=mod)

    html = rep._generate_html_content(dr, {"a": 1}, {"a": 2})
    assert "Diff Report" in html


def test_generate_stats_html():
    rep = DiffReporter()
    dr = make_diff_result(
        added=[FakeItem("1", "a", ChangeType.ADDED)],
        modified=[FakeItem("2", "b", ChangeType.MODIFIED)],
        removed=[FakeItem("3", "c", ChangeType.REMOVED)],
    )

    html = rep._generate_stats_html(dr)
    assert "Current Items" in html
    assert "Added" in html


def test_generate_changes_html_no_changes():
    rep = DiffReporter()
    dr = make_diff_result()
    html = rep._generate_changes_html(dr)
    assert "No Changes" in html


def test_generate_changes_html_with_changes():
    rep = DiffReporter()
    dr = make_diff_result(
        added=[FakeItem("1", "a", ChangeType.ADDED)],
        modified=[FakeItem("2", "b", ChangeType.MODIFIED)],
    )

    html = rep._generate_changes_html(dr)
    assert "Detailed Changes" in html


def test_generate_insights_html_non_oauth():
    rep = DiffReporter()
    dr = make_diff_result(cmd="services", insights=["  • x", "    - y"])
    html = rep._generate_insights_html(dr.key_insights, dr)
    assert "Key Insights" in html


def test_generate_insights_html_oauth():
    rep = DiffReporter()

    insights = ["grantTypes: c1, c2"]
    dr = make_diff_result(
        cmd="oauth",
        modified=[FakeItem("1", "a", ChangeType.MODIFIED)],
        insights=insights,
    )

    html = rep._generate_insights_html(dr.key_insights, dr)
    assert "modify" in html.lower() or "oauth" in html.lower()
