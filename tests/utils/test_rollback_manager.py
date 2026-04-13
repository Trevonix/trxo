from unittest.mock import MagicMock

import pytest

from trxo.utils.rollback_manager import RollbackManager


@pytest.fixture
def manager():
    return RollbackManager("scripts", realm="alpha")


def test_execute_rollback_created_success(mocker, manager):
    manager.imported_items = [{"id": "1", "action": "created"}]

    mocker.patch(
        "trxo.utils.rollback_manager.get_command_api_endpoint",
        return_value=("/scripts", None),
    )
    mocker.patch("trxo.utils.url.construct_api_url", return_value="url")

    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = None

    resp = MagicMock(status_code=204)
    client.delete.return_value = resp

    mocker.patch("httpx.Client", return_value=client)
    mocker.patch("trxo.utils.rollback_manager.info")
    mocker.patch("trxo.utils.rollback_manager.warning")

    report = manager.execute_rollback("token", "base")

    assert len(report["rolled_back"]) == 1
    assert report["rolled_back"][0]["id"] == "1"
    assert report["rolled_back"][0]["action"] == "deleted"


def test_execute_rollback_updated_success(mocker, manager):
    manager.imported_items = [
        {"id": "1", "action": "updated", "baseline": {"_id": "1"}}
    ]

    mocker.patch(
        "trxo.utils.rollback_manager.get_command_api_endpoint",
        return_value=("/scripts", None),
    )
    mocker.patch("trxo.utils.url.construct_api_url", return_value="url")

    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = None

    resp = MagicMock(status_code=200)
    client.put.return_value = resp

    mocker.patch("httpx.Client", return_value=client)
    mocker.patch("trxo.utils.rollback_manager.info")
    mocker.patch("trxo.utils.rollback_manager.warning")

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
        "trxo.utils.rollback_manager.get_command_api_endpoint",
        return_value=("/scripts", None),
    )
    mocker.patch("trxo.utils.url.construct_api_url", return_value="url")

    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = None

    resp = MagicMock(status_code=500)
    client.put.return_value = resp

    mocker.patch("httpx.Client", return_value=client)
    mocker.patch("trxo.utils.rollback_manager.info")
    mocker.patch("trxo.utils.rollback_manager.warning")

    report = manager.execute_rollback("token", "base")

    # ❌ Failed restore → not added to rolled_back
    assert len(report["rolled_back"]) == 0


def test_execute_rollback_managed_special_case(mocker):
    mgr = RollbackManager("managed", realm="alpha")

    mgr.imported_items = [{"id": "x", "action": "updated", "baseline": {"_id": "x"}}]

    mocker.patch(
        "trxo.utils.rollback_manager.get_command_api_endpoint",
        return_value=("/managed", None),
    )

    mocker.patch("trxo.utils.url.construct_api_url", return_value="url")

    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = None

    resp = MagicMock(status_code=200)
    client.put.return_value = resp

    mocker.patch("httpx.Client", return_value=client)
    mocker.patch("trxo.utils.rollback_manager.info")
    mocker.patch("trxo.utils.rollback_manager.warning")

    report = mgr.execute_rollback("token", "base")

    # ✅ FIXED: managed also restores baseline
    assert len(report["rolled_back"]) == 1
    assert report["rolled_back"][0]["id"] == "x"
    assert report["rolled_back"][0]["action"] == "restored"


def test_build_api_url_list_endpoint(mocker, manager):
    mocker.patch(
        "trxo.utils.rollback_manager.get_command_api_endpoint",
        return_value=("/scripts?_queryFilter=true", None),
    )
    mocker.patch("trxo.utils.url.construct_api_url", return_value="final")

    result = manager._build_api_url("1", "base")

    assert result == "final"


def test_build_api_url_fallback(mocker, manager):
    mocker.patch(
        "trxo.utils.rollback_manager.get_command_api_endpoint",
        side_effect=Exception("boom"),
    )
    mocker.patch("trxo.utils.url.construct_api_url", return_value="fallback")

    result = manager._build_api_url("1", "base")

    assert result == "fallback"


def test_persist_baseline_to_local(mocker, tmp_path):
    import json

    mgr = RollbackManager("scripts", realm="alpha", project_name="test_proj")
    mapping = {"1": {"_id": "1", "data": "test"}}

    config_store_mock = MagicMock()
    config_store_mock.get_project_dir.return_value = tmp_path

    mocker.patch(
        "trxo.utils.rollback_manager.ConfigStore", return_value=config_store_mock
    )
    mock_rotate = mocker.patch.object(mgr, "_rotate_local_baselines")

    mgr._persist_baseline_to_local(mapping)

    target_dir = tmp_path / "rollbacks" / "scripts" / "alpha"
    assert target_dir.exists()

    files = list(target_dir.glob("baseline_*.json"))
    assert len(files) == 1

    data = json.loads(files[0].read_text())
    assert data["data"] == mapping

    mock_rotate.assert_called_once_with(target_dir, 5)


def test_rotate_local_baselines(mocker, tmp_path):
    mgr = RollbackManager("scripts", realm="alpha", project_name="test_proj")

    # create some dummy baseline files in tmp_path
    (tmp_path / "baseline_1.json").write_text("1")
    (tmp_path / "baseline_2.json").write_text("2")
    (tmp_path / "baseline_3.json").write_text("3")

    mgr._rotate_local_baselines(tmp_path, max_files=2)

    files = list(tmp_path.glob("baseline_*.json"))
    assert len(files) == 2
    names = [f.name for f in files]
    assert "baseline_1.json" not in names
    assert "baseline_2.json" in names
    assert "baseline_3.json" in names
