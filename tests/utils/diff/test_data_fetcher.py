import json
import pytest
from pathlib import Path
from trxo.utils.diff.data_fetcher import DataFetcher, get_command_api_endpoint
from trxo.constants import DEFAULT_REALM


def test_get_command_api_endpoint_known_command():
    endpoint, response_filter = get_command_api_endpoint("scripts", realm=DEFAULT_REALM)
    assert DEFAULT_REALM in endpoint
    assert callable(response_filter)


def test_get_command_api_endpoint_unknown_command():
    endpoint, response_filter = get_command_api_endpoint("unknown")
    assert endpoint is None
    assert response_filter is None


def test_fetch_data_happy_path(mocker):
    fetcher = DataFetcher()

    mock_exporter = mocker.Mock()
    fetcher.exporter = mock_exporter

    captured = {"data": {"x": 1}}

    def fake_export_data(**kwargs):
        fetcher.exporter.save_response(captured)

    mock_exporter.export_data.side_effect = fake_export_data
    mock_exporter.save_response.side_effect = lambda data, *a, **k: Path("/tmp/x.json")

    result = fetcher.fetch_data(
        command_name="scripts",
        api_endpoint="/am/json/x",
    )

    assert result == captured


def test_fetch_data_failure_returns_none(mocker):
    fetcher = DataFetcher()

    mock_exporter = mocker.Mock()
    fetcher.exporter = mock_exporter

    mocker.patch("trxo.utils.diff.data_fetcher.error")
    mock_exporter.export_data.side_effect = Exception("boom")

    result = fetcher.fetch_data("scripts", "/am/json/x")

    assert result is None


def test_fetch_from_local_file_happy_path(tmp_path, mocker):
    fetcher = DataFetcher()

    file_path = tmp_path / "data.json"
    file_path.write_text(json.dumps({"x": 1}))

    mocker.patch.object(fetcher, "_get_storage_mode", return_value="local")

    result = fetcher.fetch_from_file_or_git(
        command_name="scripts",
        file_path=str(file_path),
    )

    assert result == {"x": 1}


def test_fetch_from_local_file_not_found(mocker):
    fetcher = DataFetcher()

    mocker.patch.object(fetcher, "_get_storage_mode", return_value="local")
    mocker.patch("trxo.utils.diff.data_fetcher.error")

    result = fetcher.fetch_from_file_or_git(
        command_name="scripts",
        file_path="missing.json",
    )

    assert result is None


def test_fetch_from_git_no_repo_returns_none(mocker, tmp_path):
    fetcher = DataFetcher()

    mocker.patch.object(fetcher, "_get_storage_mode", return_value="git")

    mock_config = mocker.Mock()
    mock_config.get_git_credentials.return_value = {
        "username": "u",
        "repo_url": "https://x/repo.git",
        "token": "t",
    }

    mocker.patch("trxo.utils.config_store.ConfigStore", return_value=mock_config)
    mocker.patch("trxo.utils.git.get_repo_base_path", return_value=tmp_path)
    mocker.patch("trxo.utils.diff.data_fetcher.warning")
    mocker.patch("trxo.utils.diff.data_fetcher.error")

    result = fetcher.fetch_from_file_or_git(
        command_name="scripts",
        branch="main",
    )

    assert result is None


def test_fetch_from_git_happy_path(mocker, tmp_path):
    fetcher = DataFetcher()

    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()

    file_path = repo_path / "scripts_alpha.json"
    file_path.write_text(json.dumps({"x": 1}))

    mocker.patch.object(fetcher, "_get_storage_mode", return_value="git")

    mock_config = mocker.Mock()
    mock_config.get_git_credentials.return_value = {
        "username": "u",
        "repo_url": "https://x/repo.git",
        "token": "t",
    }

    mocker.patch("trxo.utils.config_store.ConfigStore", return_value=mock_config)
    mocker.patch("trxo.utils.git.get_repo_base_path", return_value=tmp_path)

    result = fetcher.fetch_from_file_or_git(
        command_name="scripts",
        realm=DEFAULT_REALM,
    )

    assert result == {"x": 1}
