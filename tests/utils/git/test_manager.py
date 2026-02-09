import pytest
from unittest.mock import MagicMock

from trxo.utils.git.manager import (
    GitManager,
    setup_git_for_export,
    setup_git_for_import,
    get_git_manager,
    validate_and_setup_git_repo,
)
from trxo.constants import DEFAULT_EXPORT_BRANCH


def make_repo(branch="main"):
    repo = MagicMock()
    repo.active_branch.name = branch
    return repo


def test_git_manager_init():
    gm = GitManager("u", "t", "https://github.com/org/repo.git")
    assert gm.username == "u"
    assert gm.token == "t"
    assert gm.repo_name == "repo"


def test_git_manager_build_secure_url(mocker):
    mocker.patch("trxo.utils.git.manager.build_secure_url", return_value="secure")
    gm = GitManager("u", "t", "https://github.com/org/repo.git")
    assert gm.secure_url == "secure"


def test_git_manager_validate_credentials(mocker):
    mocker.patch(
        "trxo.utils.git.manager.validate_credentials", return_value={"ok": True}
    )
    gm = GitManager("u", "t", "https://github.com/org/repo.git")
    out = gm.validate_credentials()
    assert out == {"ok": True}


def test_git_manager_get_or_create_repo_caches(mocker):
    repo = make_repo()
    mocker.patch("trxo.utils.git.manager.get_or_create_repo", return_value=repo)

    gm = GitManager("u", "t", "https://github.com/org/repo.git")
    r1 = gm.get_or_create_repo({"x": 1})
    r2 = gm.get_or_create_repo({"x": 2})

    assert r1 is r2


def test_git_manager_ensure_branch(mocker):
    repo = make_repo()
    mocker.patch("trxo.utils.git.manager.ensure_branch", return_value=repo)

    gm = GitManager("u", "t", "https://github.com/org/repo.git")
    gm._repo_cache = repo

    out = gm.ensure_branch("dev")
    assert out is repo


def test_git_manager_commit_and_push(mocker):
    repo = make_repo()
    mocker.patch("trxo.utils.git.manager.commit_and_push", return_value=True)

    gm = GitManager("u", "t", "https://github.com/org/repo.git")
    gm._repo_cache = repo

    ok = gm.commit_and_push(["x.json"], "msg")
    assert ok is True


def test_git_manager_get_current_branch():
    repo = make_repo("dev")
    gm = GitManager("u", "t", "https://github.com/org/repo.git")
    gm._repo_cache = repo

    assert gm.get_current_branch() == "dev"


def test_git_manager_get_current_branch_without_repo():
    gm = GitManager("u", "t", "https://github.com/org/repo.git")
    with pytest.raises(RuntimeError):
        gm.get_current_branch()


def test_setup_git_for_export_default_branch(mocker):
    repo = make_repo(DEFAULT_EXPORT_BRANCH)

    mocker.patch(
        "trxo.utils.git.manager.validate_credentials", return_value={"ok": True}
    )
    mocker.patch("trxo.utils.git.manager.get_or_create_repo", return_value=repo)
    mocker.patch("trxo.utils.git.manager.ensure_branch", return_value=repo)

    gm = setup_git_for_export("u", "t", "https://github.com/org/repo.git")

    assert isinstance(gm, GitManager)


def test_setup_git_for_export_custom_branch(mocker):
    repo = make_repo("feature")

    mocker.patch(
        "trxo.utils.git.manager.validate_credentials", return_value={"ok": True}
    )
    mocker.patch("trxo.utils.git.manager.get_or_create_repo", return_value=repo)
    mocker.patch("trxo.utils.git.manager.ensure_branch", return_value=repo)

    gm = setup_git_for_export(
        "u", "t", "https://github.com/org/repo.git", branch="feature"
    )

    assert isinstance(gm, GitManager)


def test_setup_git_for_export_failure(mocker):
    mocker.patch(
        "trxo.utils.git.manager.validate_credentials", side_effect=Exception("boom")
    )

    with pytest.raises(RuntimeError):
        setup_git_for_export("u", "t", "https://github.com/org/repo.git")


def test_setup_git_for_import_branch_exists(mocker):
    repo = make_repo("dev")

    mocker.patch(
        "trxo.utils.git.manager.validate_credentials", return_value={"ok": True}
    )
    mocker.patch("trxo.utils.git.manager.get_or_create_repo", return_value=repo)
    mocker.patch(
        "trxo.utils.git.manager.branch_exists",
        return_value={"local": True, "remote": False},
    )
    mocker.patch("trxo.utils.git.manager.ensure_branch", return_value=repo)

    gm = setup_git_for_import("u", "t", "https://github.com/org/repo.git", branch="dev")
    assert isinstance(gm, GitManager)


def test_setup_git_for_import_branch_missing(mocker):
    mocker.patch(
        "trxo.utils.git.manager.validate_credentials", return_value={"ok": True}
    )
    mocker.patch("trxo.utils.git.manager.get_or_create_repo", return_value=make_repo())
    mocker.patch(
        "trxo.utils.git.manager.branch_exists",
        return_value={"local": False, "remote": False},
    )

    with pytest.raises(RuntimeError):
        setup_git_for_import("u", "t", "https://github.com/org/repo.git", branch="nope")


def test_get_git_manager():
    gm = get_git_manager("u", "t", "https://github.com/org/repo.git")
    assert isinstance(gm, GitManager)


def test_validate_and_setup_git_repo(mocker):
    repo = make_repo("main")

    mocker.patch(
        "trxo.utils.git.manager.validate_credentials", return_value={"ok": True}
    )
    mocker.patch("trxo.utils.git.manager.get_or_create_repo", return_value=repo)
    mocker.patch.object(GitManager, "ensure_work_branch", return_value=repo)

    out = validate_and_setup_git_repo("u", "t", "https://github.com/org/repo.git")

    assert out is repo
