import pytest
from unittest.mock import MagicMock

from trxo.utils.git.operations import (
    get_diff,
    is_working_tree_clean,
    get_working_tree_status,
    validate_clean_state_for_operation,
    commit_and_push,
)


def make_repo(
    dirty=False,
    untracked=None,
    changed=None,
    staged=None,
    branch="main",
    diff_returns=True,
):
    repo = MagicMock()

    repo.active_branch.name = branch
    repo.is_dirty.return_value = dirty
    repo.untracked_files = untracked or []

    changed = changed or []
    staged = staged or []

    def diff_side_effect(arg=None):
        if arg == "HEAD":
            return [MagicMock(a_path=f) for f in staged]
        if arg is None:
            return [MagicMock(a_path=f) for f in changed]
        return []

    repo.index.diff.side_effect = diff_side_effect

    if diff_returns:
        repo.git.diff.return_value = "diff content"
    else:
        repo.git.diff.side_effect = Exception("boom")

    origin = MagicMock()
    repo.remote.return_value = origin

    return repo


def test_get_diff_happy_path():
    repo = make_repo()
    assert get_diff(repo, "file.txt") == "diff content"


def test_get_diff_repo_none():
    assert get_diff(None, "file.txt") == ""


def test_get_diff_exception():
    repo = make_repo(diff_returns=False)
    assert get_diff(repo, "file.txt") == ""


def test_is_working_tree_clean_true():
    repo = make_repo(dirty=False, untracked=[])
    assert is_working_tree_clean(repo) is True


def test_is_working_tree_clean_dirty():
    repo = make_repo(dirty=True)
    assert is_working_tree_clean(repo) is False


def test_is_working_tree_clean_untracked():
    repo = make_repo(dirty=False, untracked=["a.txt"])
    assert is_working_tree_clean(repo) is False


def test_is_working_tree_clean_exception():
    repo = MagicMock()
    repo.is_dirty.side_effect = Exception("boom")
    assert is_working_tree_clean(repo) is False


def test_is_working_tree_clean_repo_none():
    with pytest.raises(RuntimeError):
        is_working_tree_clean(None)


def test_get_working_tree_status_clean():
    repo = make_repo(dirty=False, untracked=[])
    status = get_working_tree_status(repo)
    assert status["clean"] is True
    assert status["uncommitted_changes"] == []
    assert status["untracked_files"] == []


def test_get_working_tree_status_with_changes():
    repo = make_repo(
        dirty=True,
        untracked=["u.txt"],
        changed=["a.txt"],
        staged=["b.txt"],
    )

    status = get_working_tree_status(repo)
    assert status["clean"] is False
    assert set(status["uncommitted_changes"]) == {"a.txt", "b.txt"}
    assert status["untracked_files"] == ["u.txt"]


def test_get_working_tree_status_exception():
    repo = MagicMock()
    repo.untracked_files = []
    repo.is_dirty.side_effect = Exception("boom")

    with pytest.raises(RuntimeError):
        get_working_tree_status(repo)


def test_get_working_tree_status_repo_none():
    with pytest.raises(RuntimeError):
        get_working_tree_status(None)


def test_validate_clean_state_for_operation_clean():
    repo = make_repo(dirty=False, untracked=[])
    validate_clean_state_for_operation(repo, "export")


def test_validate_clean_state_for_operation_uncommitted():
    repo = make_repo(dirty=True, changed=["a.txt"])
    with pytest.raises(RuntimeError) as e:
        validate_clean_state_for_operation(repo, "export")
    assert "a.txt" in str(e.value)


def test_validate_clean_state_for_operation_untracked():
    repo = make_repo(dirty=False, untracked=["u.txt"])
    with pytest.raises(RuntimeError) as e:
        validate_clean_state_for_operation(repo, "export")
    assert "u.txt" in str(e.value)


def test_commit_and_push_success(mocker):
    repo = make_repo(staged=["a.txt"])
    mocker.patch("trxo.utils.git.operations.logger")
    ok = commit_and_push(repo, ["a.txt"], "msg")
    assert ok is True


def test_commit_and_push_no_changes():
    repo = make_repo(staged=[])
    ok = commit_and_push(repo, ["a.txt"], "msg")
    assert ok is False


def test_commit_and_push_repo_none():
    with pytest.raises(RuntimeError):
        commit_and_push(None, ["a.txt"], "msg")


def test_commit_and_push_push_failure():
    repo = make_repo(staged=["a.txt"])
    origin = MagicMock()
    origin.push.side_effect = Exception("non-fast-forward")
    repo.remote.return_value = origin

    with pytest.raises(RuntimeError):
        commit_and_push(repo, ["a.txt"], "msg")


def test_commit_and_push_generic_exception():
    repo = make_repo(staged=["a.txt"])
    repo.index.add.side_effect = Exception("boom")

    with pytest.raises(RuntimeError):
        commit_and_push(repo, ["a.txt"], "msg")
