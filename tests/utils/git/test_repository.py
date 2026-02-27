import pytest
from pathlib import Path
from unittest.mock import MagicMock

from git import GitCommandError, InvalidGitRepositoryError

from trxo.utils.git.repository import (
    get_repo_base_path,
    get_repo_path,
    init_empty_repo,
    clone_or_init_repo,
    get_or_create_repo,
)


def make_repo_mock():
    repo = MagicMock()
    repo.git = MagicMock()
    repo.index = MagicMock()
    repo.remotes = []
    repo.remote.return_value = MagicMock()
    return repo


def test_get_repo_base_path_creates_dir(tmp_path, mocker):
    mocker.patch("pathlib.Path.home", return_value=tmp_path)
    base = get_repo_base_path()
    assert base.exists()
    assert base.name == "trxo_repos"


def test_get_repo_path(tmp_path, mocker):
    mocker.patch("pathlib.Path.home", return_value=tmp_path)
    repo_path = get_repo_path("myrepo")
    assert repo_path.name == "myrepo"
    assert repo_path.parent.exists()


def test_init_empty_repo_happy_path(tmp_path, mocker):
    repo = make_repo_mock()
    mocker.patch("trxo.utils.git.repository.Repo.init", return_value=repo)

    result = init_empty_repo(
        tmp_path, "repo", "https://secure.git", {"default_branch": "main"}
    )

    repo.git.checkout.assert_called_once_with("-b", "main")
    repo.index.add.assert_called_once()
    repo.index.commit.assert_called_once()
    repo.create_remote.assert_called_once_with("origin", "https://secure.git")
    repo.remote.return_value.push.assert_called_once()
    assert result == repo


def test_init_empty_repo_remote_already_exists(tmp_path, mocker):
    repo = make_repo_mock()

    repo.create_remote.side_effect = [Exception("exists"), None]

    origin_remote = MagicMock()
    origin_remote.name = "origin"
    repo.remotes = [origin_remote]

    mocker.patch("trxo.utils.git.repository.Repo.init", return_value=repo)

    init_empty_repo(tmp_path, "repo", "url", {"default_branch": "main"})

    repo.delete_remote.assert_called_once_with("origin")
    assert repo.create_remote.call_count == 2


def test_init_empty_repo_checkout_fallback(tmp_path, mocker):
    repo = make_repo_mock()
    repo.git.checkout.side_effect = GitCommandError("x", 1)
    mocker.patch("trxo.utils.git.repository.Repo.init", return_value=repo)

    init_empty_repo(tmp_path, "repo", "url", {"default_branch": "dev"})

    repo.git.symbolic_ref.assert_called_once_with("HEAD", "refs/heads/dev")


def test_clone_or_init_repo_clone_success(tmp_path, mocker):
    repo = make_repo_mock()
    mocker.patch("trxo.utils.git.repository.Repo.clone_from", return_value=repo)
    result = clone_or_init_repo(tmp_path, "repo", "url", {})
    assert result == repo


def test_clone_or_init_repo_empty_remote_fallback(tmp_path, mocker):
    mocker.patch(
        "trxo.utils.git.repository.Repo.clone_from",
        side_effect=GitCommandError("x", 1, "remote HEAD refers to nonexistent ref"),
    )

    init_repo = make_repo_mock()
    mocker.patch("trxo.utils.git.repository.init_empty_repo", return_value=init_repo)

    result = clone_or_init_repo(tmp_path, "repo", "url", {})
    assert result == init_repo


def test_clone_or_init_repo_clone_failure(tmp_path, mocker):
    mocker.patch(
        "trxo.utils.git.repository.Repo.clone_from",
        side_effect=GitCommandError("x", 1, "boom"),
    )

    with pytest.raises(RuntimeError):
        clone_or_init_repo(tmp_path, "repo", "url", {})


def test_get_or_create_repo_existing_valid_repo(tmp_path, mocker):
    repo_dir = tmp_path / "repo"
    (repo_dir / ".git").mkdir(parents=True)

    repo = make_repo_mock()
    mocker.patch("trxo.utils.git.repository.Repo", return_value=repo)

    result = get_or_create_repo(repo_dir, "repo", "url", {})

    repo.remote.assert_called_once_with("origin")
    repo.remote.return_value.set_url.assert_called_once_with("url")
    assert result == repo


def test_get_or_create_repo_existing_invalid_repo(tmp_path, mocker):
    repo_dir = tmp_path / "repo"
    (repo_dir / ".git").mkdir(parents=True)

    mocker.patch(
        "trxo.utils.git.repository.Repo", side_effect=InvalidGitRepositoryError
    )

    clone_repo = make_repo_mock()
    mocker.patch(
        "trxo.utils.git.repository.clone_or_init_repo", return_value=clone_repo
    )

    result = get_or_create_repo(repo_dir, "repo", "url", {})
    assert result == clone_repo


def test_get_or_create_repo_existing_repo_remote_update_fails(tmp_path, mocker):
    repo_dir = tmp_path / "repo"
    (repo_dir / ".git").mkdir(parents=True)

    repo = make_repo_mock()
    repo.remote.return_value.set_url.side_effect = Exception("boom")
    mocker.patch("trxo.utils.git.repository.Repo", return_value=repo)

    result = get_or_create_repo(repo_dir, "repo", "url", {})
    assert result == repo


def test_get_or_create_repo_not_existing(tmp_path, mocker):
    clone_repo = make_repo_mock()
    mocker.patch(
        "trxo.utils.git.repository.clone_or_init_repo", return_value=clone_repo
    )

    result = get_or_create_repo(tmp_path / "repo", "repo", "url", {})
    assert result == clone_repo
