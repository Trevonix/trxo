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
