from unittest.mock import MagicMock

import pytest

from trxo_lib.state.rollback import RollbackManager


@pytest.fixture
def manager():
    return RollbackManager("scripts", realm="alpha")


def test_execute_rollback_created_success(mocker, manager):
    manager.imported_items = [{"id": "1", "action": "created"}]

    mocker.patch(
        "trxo_lib.state.rollback.manager.get_command_api_endpoint",
        return_value=("/scripts", None),
    )
    mocker.patch("trxo_lib.core.url.construct_api_url", return_value="url")

    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = None

    resp = MagicMock(status_code=204)
    client.delete.return_value = resp

    mocker.patch("httpx.Client", return_value=client)
    mocker.patch("trxo_lib.state.rollback.manager.logger.info")
    mocker.patch("trxo_lib.state.rollback.manager.logger.warning")

    report = manager.execute_rollback("token", "base")

    assert len(report["rolled_back"]) == 1
    assert report["rolled_back"][0]["id"] == "1"
    assert report["rolled_back"][0]["action"] == "deleted"


def test_execute_rollback_updated_success(mocker, manager):
    manager.imported_items = [
        {"id": "1", "action": "updated", "baseline": {"_id": "1"}}
    ]

    mocker.patch(
        "trxo_lib.state.rollback.manager.get_command_api_endpoint",
        return_value=("/scripts", None),
    )
    mocker.patch("trxo_lib.core.url.construct_api_url", return_value="url")

    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = None

    resp = MagicMock(status_code=200)
    client.put.return_value = resp

    mocker.patch("httpx.Client", return_value=client)
    mocker.patch("trxo_lib.state.rollback.manager.logger.info")
    mocker.patch("trxo_lib.state.rollback.manager.logger.warning")

    report = manager.execute_rollback("token", "base")

    # ✅ FIXED: updated items are now restored
    assert len(report["rolled_back"]) == 1
    assert report["rolled_back"][0]["id"] == "1"
    assert report["rolled_back"][0]["action"] == "restored"


def test_execute_rollback_updated_no_change(mocker, manager):
    manager.imported_items = [
        {"id": "1", "action": "updated", "baseline": {"_id": "1"}}
    ]

    mocker.patch(
        "trxo_lib.state.rollback.manager.get_command_api_endpoint",
        return_value=("/scripts", None),
    )
    mocker.patch("trxo_lib.core.url.construct_api_url", return_value="url")

    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = None

    resp = MagicMock(status_code=500)
    client.put.return_value = resp

    mocker.patch("httpx.Client", return_value=client)
    mocker.patch("trxo_lib.state.rollback.manager.logger.info")
    mocker.patch("trxo_lib.state.rollback.manager.logger.warning")

    report = manager.execute_rollback("token", "base")

    # ❌ Failed restore → not added to rolled_back
    assert len(report["rolled_back"]) == 0


def test_execute_rollback_managed_special_case(mocker):
    mgr = RollbackManager("managed", realm="alpha")

    mgr.imported_items = [{"id": "x", "action": "updated", "baseline": {"_id": "x"}}]

    mocker.patch(
        "trxo_lib.state.rollback.manager.get_command_api_endpoint",
        return_value=("/managed", None),
    )

    mocker.patch("trxo_lib.core.url.construct_api_url", return_value="url")

    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = None

    resp = MagicMock(status_code=200)
    client.put.return_value = resp

    mocker.patch("httpx.Client", return_value=client)
    mocker.patch("trxo_lib.state.rollback.manager.logger.info")
    mocker.patch("trxo_lib.state.rollback.manager.logger.warning")

    report = mgr.execute_rollback("token", "base")

    # ✅ FIXED: managed also restores baseline
    assert len(report["rolled_back"]) == 1
    assert report["rolled_back"][0]["id"] == "x"
    assert report["rolled_back"][0]["action"] == "restored"


def test_create_baseline_snapshot_success(mocker, manager):
    mocker.patch("trxo_lib.state.rollback.manager.get_command_api_endpoint", return_value=("/scripts", None))
    mock_fetcher = mocker.patch("trxo_lib.state.rollback.manager.DataFetcher")
    mock_fetcher.return_value.fetch_data.return_value = {"result": [{"_id": "s1"}]}
    
    # Mock httpx.Client for full config fetch inside _snapshot_generic
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.get.return_value = MagicMock(status_code=200)
    mock_client.get.return_value.json.return_value = {"_id": "s1", "full": "data"}
    mocker.patch("httpx.Client", return_value=mock_client)

    # Mock script capture
    mocker.patch.object(manager, "_capture_scripts")
    # Mock persistence
    mocker.patch.object(manager, "_persist_baseline")
    
    res = manager.create_baseline_snapshot("token", "http://base")
    assert res is True
    assert "s1" in manager.baseline_snapshot

def test_capture_scripts_recursion(mocker, manager):
    manager.realm = "alpha"
    data = {
        "authnContextMapperScript": "12345678-1234-1234-1234-123456789012",
        "nested": [{"valScript": "87654321-4321-4321-4321-210987654321"}],
        "ignored": "too-short",
        "empty": "[Empty]"
    }
    
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.get.return_value = MagicMock(status_code=200)
    mock_client.get.return_value.json.return_value = {"_id": "script-data"}
    mocker.patch("httpx.Client", return_value=mock_client)
    
    manager._capture_scripts(data, "token", "http://base")
    assert len(manager.baseline_snapshot["scripts"]) == 2

def test_snapshot_saml(mocker, manager):
    manager.command_name = "saml"
    data = {
        "hosted": [{"_id": "h1", "entityId": "h1-alt"}],
        "remote": [{"_id": "r1"}]
    }
    mocker.patch.object(manager, "_persist_baseline")
    res = manager._snapshot_saml(data, None)
    assert res is True
    assert "h1" in manager.baseline_snapshot
    assert "h1-alt" in manager.baseline_snapshot
    assert "r1" in manager.baseline_snapshot
    assert manager.baseline_snapshot["h1"]["_saml_location"] == "hosted"

def test_restore_full_baseline(mocker, manager):
    manager.baseline_snapshot = {
        "1": {"val": "x"},
        "scripts": {"s1": {"name": "s1", "script": "print(1)", "context": "ctx"}}
    }
    manager.imported_items = [] # Triggers full baseline restore
    
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.put.return_value = MagicMock(status_code=200)
    mocker.patch("httpx.Client", return_value=mock_client)
    mocker.patch.object(manager, "_build_api_url", return_value="url")
    mocker.patch.object(manager, "_build_auth_headers", return_value={})
    
    report = manager.execute_rollback("token", "base")
    assert len(report["rolled_back"]) == 2

def test_persist_baseline_to_local_success(mocker, manager):
    mock_config = MagicMock()
    from pathlib import Path
    mock_config.base_dir = Path("/tmp/trxo_test")
    mocker.patch("trxo_lib.state.rollback.manager.ConfigStore", return_value=mock_config)
    
    # Mock Path methods to avoid real FS access
    mocker.patch("pathlib.Path.mkdir")
    mocker.patch("pathlib.Path.write_text")
    
    path = manager._persist_baseline_to_local({"item1": {"val": 1}})
    assert "baseline_alpha" in path

def test_rollback_delete_policy_fallback(mocker, manager):
    manager.command_name = "policies"
    manager.realm = "alpha"
    
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    # First DELETE fails with 404, fallback succeeds with 200
    mock_client.delete.side_effect = [
        MagicMock(status_code=404),
        MagicMock(status_code=200)
    ]
    mocker.patch("httpx.Client", return_value=mock_client)
    mocker.patch.object(manager, "_build_auth_headers", return_value={})
    
    report = {"rolled_back": [], "errors": []}
    manager._rollback_delete("p1", "p1", "data", "url", {}, "token", "base", report)
    
    assert len(report["rolled_back"]) == 1
    assert report["rolled_back"][0]["action"] == "deleted"


def test_build_api_url_list_endpoint(mocker, manager):
    # Set to a command that doesn't trigger special cases (like nodes, saml, scripts, etc.)
    manager.command_name = "test_command"
    mocker.patch(
        "trxo_lib.state.rollback.url_builder.get_command_api_endpoint",
        return_value=("/test_command?_queryFilter=true", None),
    )
    mocker.patch(
        "trxo_lib.state.rollback.url_builder.construct_api_url", return_value="final"
    )

    result = manager._build_api_url("1", "base")

    assert result == "final"


def test_build_api_url_fallback(mocker, manager):
    manager.command_name = "test_command"
    mocker.patch(
        "trxo_lib.state.rollback.url_builder.get_command_api_endpoint",
        side_effect=Exception("boom"),
    )
    mocker.patch(
        "trxo_lib.state.rollback.url_builder.construct_api_url", return_value="fallback"
    )

    result = manager._build_api_url("1", "base")

    assert result == "fallback"
