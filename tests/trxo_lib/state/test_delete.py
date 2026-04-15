"""Tests for the refactored trxo_lib.state.delete.DeletionManager.

The manager is now presentation-agnostic: no console calls, no user prompts.
It returns pure data dicts.
"""

from unittest.mock import MagicMock

from trxo_lib.state.delete import DeletionManager


class FakeDiffItem:
    def __init__(self, item_id, item_name=None):
        self.item_id = item_id
        self.item_name = item_name


class FakeDiffResult:
    def __init__(self, removed_items):
        self.removed_items = removed_items


# ── get_items_to_delete ───────────────────────────────────────────────


def test_get_items_to_delete():
    items = [FakeDiffItem("1"), FakeDiffItem("2")]
    diff_result = FakeDiffResult(items)

    mgr = DeletionManager()
    result = mgr.get_items_to_delete(diff_result)

    assert result == items


def test_get_items_to_delete_empty():
    diff_result = FakeDiffResult([])

    mgr = DeletionManager()
    result = mgr.get_items_to_delete(diff_result)

    assert result == []


# ── execute_deletions ─────────────────────────────────────────────────


def test_execute_deletions_all_success():
    delete_func = MagicMock(return_value=True)
    items = [FakeDiffItem("1", "Item One"), FakeDiffItem("2", "Item Two")]

    mgr = DeletionManager()
    summary = mgr.execute_deletions(items, delete_func, "token", "url")

    assert summary["deleted_count"] == 2
    assert summary["failed_count"] == 0
    assert summary["deleted_items"] == ["1", "2"]
    assert summary["failed_deletions"] == []


def test_execute_deletions_partial_failure():
    delete_func = MagicMock(side_effect=[True, False])
    items = [FakeDiffItem("1"), FakeDiffItem("2")]

    mgr = DeletionManager()
    summary = mgr.execute_deletions(items, delete_func, "token", "url")

    assert summary["deleted_count"] == 1
    assert summary["failed_count"] == 1
    assert summary["deleted_items"] == ["1"]
    assert summary["failed_deletions"][0]["id"] == "2"


def test_execute_deletions_exception():
    def boom(item_id, token, url):
        raise Exception("boom")

    items = [FakeDiffItem("1")]

    mgr = DeletionManager()
    summary = mgr.execute_deletions(items, boom, "token", "url")

    assert summary["deleted_count"] == 0
    assert summary["failed_count"] == 1
    assert summary["failed_deletions"][0]["id"] == "1"
    assert "boom" in summary["failed_deletions"][0]["error"]


def test_execute_deletions_no_items():
    delete_func = MagicMock()

    mgr = DeletionManager()
    summary = mgr.execute_deletions([], delete_func, "token", "url")

    assert summary["deleted_count"] == 0
    assert summary["failed_count"] == 0
    delete_func.assert_not_called()
