import json

from trxo_lib.config.constants import DEFAULT_REALM
from trxo_lib.state.diff.data_fetcher import DataFetcher, get_command_api_endpoint


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

    mock_result = mocker.Mock()
    mock_result.data = captured

    mock_exporter.export_data.return_value = mock_result

    result = fetcher.fetch_data(
        command_name="scripts",
        api_endpoint="/am/json/x",
    )

    assert result == captured["data"]


def test_fetch_data_failure_returns_none(mocker):
    fetcher = DataFetcher()

    mock_exporter = mocker.Mock()
    fetcher.exporter = mock_exporter

    mocker.patch("trxo_lib.state.diff.data_fetcher.logger")
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
    mocker.patch("trxo_lib.state.diff.data_fetcher.logger")

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

    mocker.patch("trxo_lib.config.config_store.ConfigStore", return_value=mock_config)
    mocker.patch("trxo_lib.git.get_repo_base_path", return_value=tmp_path)
    mocker.patch("trxo_lib.state.diff.data_fetcher.logger")

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

    mocker.patch("trxo_lib.config.config_store.ConfigStore", return_value=mock_config)
    mocker.patch("trxo_lib.git.get_repo_base_path", return_value=tmp_path)

    result = fetcher.fetch_from_file_or_git(
        command_name="scripts",
        realm=DEFAULT_REALM,
    )

    assert result == {"x": 1}


def test_process_nodes_response():
    from trxo_lib.state.diff.data_fetcher import _process_nodes_response
    filter_func = _process_nodes_response(None, "alpha")
    data = {"result": [{"_id": "n1", "val": 1}, {"_id": "n2"}]}
    res = filter_func(data)
    assert len(res["nodes"]) == 2
    assert res["nodes"]["n1"]["val"] == 1


def test_process_email_templates_response():
    from trxo_lib.state.diff.data_fetcher import _process_email_templates_response
    filter_func = _process_email_templates_response(None, "alpha")
    data = {"result": [{"_id": "e1"}]}
    res = filter_func(data)
    assert res["result"] == [{"_id": "e1"}]


def test_fetch_nodes_direct_success(mocker):
    from trxo_lib.state.diff.data_fetcher import _fetch_nodes_direct
    mock_exporter = mocker.Mock()
    mock_exporter._construct_api_url.return_value = "http://url"
    mock_resp = mocker.Mock()
    mock_resp.json.return_value = {"result": [{"_id": "n1"}]}
    mock_exporter.make_http_request.return_value = mock_resp
    
    res = _fetch_nodes_direct(mock_exporter, "alpha", "base", {})
    assert "nodes" in res
    assert "n1" in res["nodes"]


def test_fetch_data_nodes_special(mocker):
    fetcher = DataFetcher()
    mock_exporter = mocker.Mock()
    fetcher.exporter = mock_exporter
    mock_exporter.initialize_auth.return_value = ("token", "http://base")
    mock_exporter.build_auth_headers.return_value = {"Authorization": "token"}
    
    mock_direct = mocker.patch("trxo_lib.state.diff.data_fetcher._fetch_nodes_direct")
    mock_direct.return_value = {"nodes": {}}
    res = fetcher.fetch_data("nodes", "/endpoint")
    assert res == {"nodes": {}}


def test_fetch_data_specialized_commands(mocker):
    fetcher = DataFetcher()
    mock_exporter = mocker.Mock()
    fetcher.exporter = mock_exporter
    mock_exporter.export_data.return_value = mocker.Mock(data={"data": {"ok": True}})
    
    # Test for OAuth
    mock_oauth = mocker.patch("trxo_lib.state.diff.data_fetcher.OAuthExporter")
    fetcher.fetch_data("oauth", "/endpoint")
    assert mock_oauth.called


def test_fetch_from_local_file_special_logic(tmp_path):
    fetcher = DataFetcher()
    file_path = tmp_path / "apps.json"
    file_path.write_text(json.dumps({
        "data": {
            "applications": [{"_id": "app1"}]
        }
    }))
    
    res = fetcher._fetch_from_local_file(str(file_path), command_name="applications")
    assert res == {"result": [{"_id": "app1"}]}
