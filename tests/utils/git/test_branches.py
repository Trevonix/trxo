import pytest
from unittest.mock import MagicMock

from trxo.utils.git.branches import (
    get_default_branch,
    check_branch_sync_status,
    validate_branch_sync_for_operation,
    ensure_branch,
    list_branches,
    branch_exists,
)


def make_repo(
    local_branches=("main",),
    remote_branches=("main",),
    diverged=False,
    behind=0,
    ahead=0,
):
    repo = MagicMock()

    # ----- heads (acts like list + dict) -----
    heads_list = []
    heads_map = {}

    for name in local_branches:
        h = MagicMock()
        h.name = name
        h.commit = MagicMock(name=f"{name}_commit")
        heads_list.append(h)
        heads_map[name] = h

    class Heads(list):
        def __getitem__(self, key):
            if isinstance(key, str):
                return heads_map[key]
            return super().__getitem__(key)

    repo.heads = Heads(heads_list)

    # ----- origin refs (acts like list + dict) -----
    origin = MagicMock()
    origin.name = "origin"

    refs_list = []
    refs_map = {}

    for name in remote_branches:
        ref = MagicMock()
        ref.name = f"origin/{name}"
        ref.commit = MagicMock(name=f"{name}_remote_commit")
        refs_list.append(ref)
        refs_map[name] = ref

    class Refs(list):
        def __getitem__(self, key):
            if isinstance(key, str):
                return refs_map[key]
            return super().__getitem__(key)

    origin.refs = Refs(refs_list)
    origin.fetch = MagicMock()

    repo.remote.return_value = origin

    def iter_commits(expr):
        if diverged:
            if expr.startswith("main..origin/main"):
                return [1] * behind
            if expr.startswith("origin/main..main"):
                return [1] * ahead
        if "origin/main" in expr and behind > 0:
            return [1] * behind
        if "main" in expr and ahead > 0:
            return [1] * ahead
        return []

    repo.iter_commits.side_effect = iter_commits
    repo.git.checkout = MagicMock()
    repo.git.pull = MagicMock()
    repo.git.fetch = MagicMock()

    return repo


def test_get_default_branch_from_local_only():
    repo = make_repo(local_branches=("dev",))
    assert get_default_branch(repo) == "dev"


def test_get_default_branch_fallback_main():
    repo = make_repo(local_branches=("main",))
    assert get_default_branch(repo) == "main"


def test_check_branch_sync_status_in_sync():
    repo = make_repo(local_branches=("main",), remote_branches=("main",))
    repo.heads[0].commit = repo.remote().refs[0].commit
    status = check_branch_sync_status(repo, "main")
    assert status["in_sync"] is True


def test_check_branch_sync_status_behind():
    repo = make_repo(local_branches=("main",), remote_branches=("main",), behind=2)
    status = check_branch_sync_status(repo, "main")
    assert status["behind"] == 2


def test_check_branch_sync_status_diverged():
    repo = make_repo(
        local_branches=("main",),
        remote_branches=("main",),
        diverged=True,
        behind=1,
        ahead=1,
    )
    status = check_branch_sync_status(repo, "main")
    assert status["diverged"] is True


def test_validate_branch_sync_for_operation_pulls_when_behind(mocker):
    repo = make_repo(local_branches=("main",), remote_branches=("main",), behind=1)
    mocker.patch(
        "trxo.utils.git.branches.check_branch_sync_status",
        return_value={
            "exists_local": True,
            "exists_remote": True,
            "behind": 1,
            "ahead": 0,
            "diverged": False,
            "in_sync": False,
        },
    )

    validate_branch_sync_for_operation(repo, "main", "export")
    repo.git.pull.assert_called()


def test_validate_branch_sync_for_operation_diverged_raises(mocker):
    repo = make_repo(local_branches=("main",), remote_branches=("main",))
    mocker.patch(
        "trxo.utils.git.branches.check_branch_sync_status",
        return_value={
            "exists_local": True,
            "exists_remote": True,
            "behind": 1,
            "ahead": 1,
            "diverged": True,
            "in_sync": False,
        },
    )

    with pytest.raises(RuntimeError):
        validate_branch_sync_for_operation(repo, "main", "export")


def test_ensure_branch_existing_local(mocker):
    repo = make_repo(local_branches=("dev",))
    mocker.patch("trxo.utils.git.branches.validate_clean_state_for_operation")
    ensure_branch(repo, "dev")
    repo.git.checkout.assert_called_with("dev")


def test_ensure_branch_checkout_remote(mocker):
    repo = make_repo(local_branches=(), remote_branches=("dev",))
    mocker.patch("trxo.utils.git.branches.validate_clean_state_for_operation")
    ensure_branch(repo, "dev")
    repo.git.checkout.assert_called_with("-b", "dev", "origin/dev")


def test_ensure_branch_create_from_default(mocker):
    repo = make_repo(local_branches=("main",), remote_branches=("main",))
    mocker.patch("trxo.utils.git.branches.validate_clean_state_for_operation")
    ensure_branch(repo, "feature-x")
    repo.git.checkout.assert_any_call("-b", "feature-x")


def test_list_branches_basic():
    repo = make_repo(local_branches=("a", "b"), remote_branches=("c",))
    result = list_branches(repo)
    assert result["local"] == ["a", "b"]
    assert "c" in result["remote"]


def test_branch_exists_local_only():
    repo = make_repo(local_branches=("x",), remote_branches=())
    result = branch_exists(repo, "x")
    assert result["local"] is True
    assert result["remote"] is False


def test_branch_exists_remote_only():
    repo = make_repo(local_branches=(), remote_branches=("x",))
    result = branch_exists(repo, "x")
    assert result["local"] is False
    assert result["remote"] is True


def test_branch_exists_none():
    repo = make_repo(local_branches=(), remote_branches=())
    result = branch_exists(repo, "missing")
    assert result["local"] is False
    assert result["remote"] is False
