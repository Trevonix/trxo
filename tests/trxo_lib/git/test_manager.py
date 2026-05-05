import pytest
from unittest.mock import MagicMock, patch
from trxo_lib.git.manager import GitManager, setup_git_for_export, setup_git_for_import, validate_and_setup_git_repo
from trxo_lib.exceptions import TrxoGitError

@pytest.fixture
def git_manager():
    with patch("trxo_lib.git.manager.get_repo_path", return_value=MagicMock()):
        return GitManager("user", "token", "https://github.com/org/repo.git")

def test_git_manager_init(git_manager):
    assert git_manager.repo_name == "repo"
    assert "user:token@github.com" in git_manager.secure_url

def test_get_or_create_repo_cached(git_manager):
    mock_repo = MagicMock()
    git_manager._repo_cache = mock_repo
    assert git_manager.get_or_create_repo({}) == mock_repo

def test_get_or_create_repo_new(git_manager):
    with patch("trxo_lib.git.manager.get_or_create_repo") as mock_get:
        mock_repo = MagicMock()
        mock_get.return_value = mock_repo
        res = git_manager.get_or_create_repo({"info": "val"})
        assert res == mock_repo
        assert git_manager._repo_cache == mock_repo

def test_ensure_work_branch_no_repo(git_manager):
    with pytest.raises(TrxoGitError, match="Repository not initialized"):
        git_manager.ensure_work_branch()

def test_ensure_work_branch_success(git_manager):
    mock_repo = MagicMock()
    h = MagicMock()
    h.name = "main"
    mock_repo.heads = [h]
    git_manager._repo_cache = mock_repo
    with patch.object(git_manager, "_get_default_branch", return_value="main"):
        res = git_manager.ensure_work_branch("main", validate=False)
        assert res == mock_repo
        mock_repo.git.checkout.assert_called_with("main")

def test_ensure_work_branch_validate(git_manager):
    mock_repo = MagicMock()
    git_manager._repo_cache = mock_repo
    with patch("trxo_lib.git.manager.ensure_branch", return_value=mock_repo) as mock_ensure:
        git_manager.ensure_work_branch("feat", validate=True)
        mock_ensure.assert_called()

def test_setup_git_for_export_success():
    with patch("trxo_lib.git.manager.GitManager") as mock_mgr_class:
        mock_mgr = mock_mgr_class.return_value
        mock_mgr.validate_credentials.return_value = {}
        setup_git_for_export("u", "t", "url", branch="feat")
        mock_mgr.ensure_branch.assert_called()

def test_setup_git_for_import_success():
    with patch("trxo_lib.git.manager.GitManager") as mock_mgr_class:
        mock_mgr = mock_mgr_class.return_value
        mock_mgr.validate_credentials.return_value = {}
        mock_mgr.branch_exists.return_value = {"local": True, "remote": False}
        setup_git_for_import("u", "t", "url", branch="feat")
        mock_mgr.ensure_branch.assert_called()

def test_wrappers(git_manager):
    mock_repo = MagicMock()
    git_manager._repo_cache = mock_repo
    with patch("trxo_lib.git.manager.list_branches") as m:
        git_manager.list_branches()
        m.assert_called_with(mock_repo)
    with patch("trxo_lib.git.manager.get_diff") as m:
        git_manager.get_diff("path")
        m.assert_called_with(mock_repo, "path")
    with patch("trxo_lib.git.manager.commit_and_push") as m:
        git_manager.commit_and_push(["p"], "msg")
        m.assert_called_with(mock_repo, ["p"], "msg")

def test_validate_and_setup_git_repo():
    with patch("trxo_lib.git.manager.GitManager") as mock_mgr_class:
        mock_mgr = mock_mgr_class.return_value
        mock_mgr.validate_credentials.return_value = {}
        mock_mgr.get_or_create_repo.return_value = MagicMock()
        validate_and_setup_git_repo("u", "t", "url")
        mock_mgr.ensure_branch.assert_called()

def test_create_initial_commit(git_manager, tmp_path):
    mock_repo = MagicMock()
    git_manager.local_path = tmp_path
    git_manager._create_initial_commit(mock_repo)
    assert (tmp_path / "README.md").exists()
    mock_repo.index.add.assert_called()
    mock_repo.index.commit.assert_called()
