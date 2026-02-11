import pytest
from unittest.mock import MagicMock

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

    assert len(report["rolled_back"]) == 1
    assert report["rolled_back"][0]["id"] == "1"
    assert report["rolled_back"][0]["action"] == "restored"


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

    assert len(report["rolled_back"]) == 1
    assert report["rolled_back"][0]["id"] == "1"
    assert report["rolled_back"][0]["action"] == "restored"


def test_execute_rollback_managed_special_case(mocker):
    mgr = RollbackManager("managed", realm="alpha")
    mgr.raw_baseline_data = {"data": {"x": 1}}

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

    assert len(report["rolled_back"]) == 1
    assert report["rolled_back"][0]["action"] == "restored_managed_config"


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
