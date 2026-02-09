import pytest
from unittest.mock import MagicMock

from trxo.utils.deletion_manager import DeletionManager


class FakeDiffItem:
    def __init__(self, item_id, item_name=None):
        self.item_id = item_id
        self.item_name = item_name


class FakeDiffResult:
    def __init__(self, removed_items):
        self.removed_items = removed_items


def test_get_items_to_delete():
    items = [FakeDiffItem("1"), FakeDiffItem("2")]
    diff_result = FakeDiffResult(items)

    mgr = DeletionManager()
    result = mgr.get_items_to_delete(diff_result)

    assert result == items


def test_confirm_deletions_no_items(mocker):
    mocker.patch("trxo.utils.deletion_manager.info")
    mgr = DeletionManager()

    ok = mgr.confirm_deletions([], "scripts", force=False)

    assert ok is True


def test_confirm_deletions_force_true(mocker):
    mocker.patch("trxo.utils.deletion_manager.warning")
    mocker.patch("trxo.utils.deletion_manager.info")

    mgr = DeletionManager()
    items = [FakeDiffItem("1", "one")]

    ok = mgr.confirm_deletions(items, "scripts", force=True)

    assert ok is True


def test_confirm_deletions_user_confirms(mocker):
    mocker.patch("trxo.utils.deletion_manager.warning")
    mocker.patch("trxo.utils.deletion_manager.info")
    mocker.patch("typer.confirm", return_value=True)

    mgr = DeletionManager()
    items = [FakeDiffItem("1", "one")]

    ok = mgr.confirm_deletions(items, "scripts", force=False)

    assert ok is True


def test_confirm_deletions_user_cancels(mocker):
    mocker.patch("trxo.utils.deletion_manager.warning")
    mocker.patch("trxo.utils.deletion_manager.info")
    mocker.patch("typer.confirm", return_value=False)

    mgr = DeletionManager()
    items = [FakeDiffItem("1", "one")]

    ok = mgr.confirm_deletions(items, "scripts", force=False)

    assert ok is False


def test_execute_deletions_all_success(mocker):
    mocker.patch("trxo.utils.deletion_manager.info")
    mocker.patch("trxo.utils.deletion_manager.success")
    mocker.patch("trxo.utils.deletion_manager.error")

    delete_func = MagicMock(return_value=True)
    items = [FakeDiffItem("1"), FakeDiffItem("2")]

    mgr = DeletionManager()
    summary = mgr.execute_deletions(items, delete_func, "token", "url")

    assert summary["deleted_count"] == 2
    assert summary["failed_count"] == 0
    assert summary["deleted_items"] == ["1", "2"]
    assert summary["failed_deletions"] == []


def test_execute_deletions_partial_failure(mocker):
    mocker.patch("trxo.utils.deletion_manager.info")
    mocker.patch("trxo.utils.deletion_manager.success")
    mocker.patch("trxo.utils.deletion_manager.error")

    delete_func = MagicMock(side_effect=[True, False])
    items = [FakeDiffItem("1"), FakeDiffItem("2")]

    mgr = DeletionManager()
    summary = mgr.execute_deletions(items, delete_func, "token", "url")

    assert summary["deleted_count"] == 1
    assert summary["failed_count"] == 1
    assert summary["deleted_items"] == ["1"]
    assert summary["failed_deletions"][0]["id"] == "2"


def test_execute_deletions_exception(mocker):
    mocker.patch("trxo.utils.deletion_manager.info")
    mocker.patch("trxo.utils.deletion_manager.success")
    mocker.patch("trxo.utils.deletion_manager.error")

    def boom(item_id, token, url):
        raise Exception("boom")

    items = [FakeDiffItem("1")]

    mgr = DeletionManager()
    summary = mgr.execute_deletions(items, boom, "token", "url")

    assert summary["deleted_count"] == 0
    assert summary["failed_count"] == 1
    assert summary["failed_deletions"][0]["id"] == "1"
    assert "boom" in summary["failed_deletions"][0]["error"]


def test_print_summary_only_success(mocker):
    success_mock = mocker.patch("trxo.utils.deletion_manager.success")
    error_mock = mocker.patch("trxo.utils.deletion_manager.error")

    mgr = DeletionManager()
    mgr.print_summary(
        {
            "deleted_count": 2,
            "failed_count": 0,
            "deleted_items": ["1", "2"],
            "failed_deletions": [],
        }
    )

    success_mock.assert_called_once()
    error_mock.assert_not_called()


def test_print_summary_only_failures(mocker):
    success_mock = mocker.patch("trxo.utils.deletion_manager.success")
    error_mock = mocker.patch("trxo.utils.deletion_manager.error")

    mgr = DeletionManager()
    mgr.print_summary(
        {
            "deleted_count": 0,
            "failed_count": 1,
            "deleted_items": [],
            "failed_deletions": [{"id": "1", "error": "boom"}],
        }
    )

    success_mock.assert_not_called()
    assert error_mock.call_count >= 2


def test_print_summary_mixed(mocker):
    success_mock = mocker.patch("trxo.utils.deletion_manager.success")
    error_mock = mocker.patch("trxo.utils.deletion_manager.error")

    mgr = DeletionManager()
    mgr.print_summary(
        {
            "deleted_count": 1,
            "failed_count": 1,
            "deleted_items": ["1"],
            "failed_deletions": [{"id": "2", "error": "fail"}],
        }
    )

    success_mock.assert_called_once()
    assert error_mock.call_count >= 2
