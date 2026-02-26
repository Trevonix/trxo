import pytest
from unittest.mock import MagicMock

from trxo.utils.imports.sync_handler import SyncHandler


def test_handle_sync_deletions_diff_fails(mocker):
    mocker.patch("trxo.utils.imports.sync_handler.info")
    mocker.patch("trxo.utils.imports.sync_handler.warning")
    mocker.patch("trxo.utils.imports.sync_handler.success")

    diff_manager = MagicMock()
    diff_manager.perform_diff.return_value = None
    mocker.patch(
        "trxo.utils.imports.sync_handler.DiffManager", return_value=diff_manager
    )

    result = SyncHandler.handle_sync_deletions(
        command_name="scripts",
        item_type="scripts",
        delete_func=MagicMock(),
        token="t",
        base_url="url",
    )

    assert result is None


def test_handle_sync_deletions_no_items_to_delete(mocker):
    mocker.patch("trxo.utils.imports.sync_handler.info")
    mocker.patch("trxo.utils.imports.sync_handler.warning")
    success_mock = mocker.patch("trxo.utils.imports.sync_handler.success")

    diff_manager = MagicMock()
    diff_manager.perform_diff.return_value = {"removed": []}
    mocker.patch(
        "trxo.utils.imports.sync_handler.DiffManager", return_value=diff_manager
    )

    deletion_manager = MagicMock()
    deletion_manager.get_items_to_delete.return_value = []
    mocker.patch(
        "trxo.utils.imports.sync_handler.DeletionManager", return_value=deletion_manager
    )

    result = SyncHandler.handle_sync_deletions(
        command_name="scripts",
        item_type="scripts",
        delete_func=MagicMock(),
        token="t",
        base_url="url",
    )

    assert result is None
    success_mock.assert_called_once()


def test_handle_sync_deletions_user_cancels(mocker):
    mocker.patch("trxo.utils.imports.sync_handler.info")
    warning_mock = mocker.patch("trxo.utils.imports.sync_handler.warning")

    diff_manager = MagicMock()
    diff_manager.perform_diff.return_value = {"removed": [{"_id": "1"}]}
    mocker.patch(
        "trxo.utils.imports.sync_handler.DiffManager", return_value=diff_manager
    )

    deletion_manager = MagicMock()
    deletion_manager.get_items_to_delete.return_value = [{"_id": "1"}]
    deletion_manager.confirm_deletions.return_value = False
    mocker.patch(
        "trxo.utils.imports.sync_handler.DeletionManager", return_value=deletion_manager
    )

    result = SyncHandler.handle_sync_deletions(
        command_name="scripts",
        item_type="scripts",
        delete_func=MagicMock(),
        token="t",
        base_url="url",
    )

    assert result is None
    warning_mock.assert_called_once()


def test_handle_sync_deletions_success(mocker):
    mocker.patch("trxo.utils.imports.sync_handler.info")
    mocker.patch("trxo.utils.imports.sync_handler.warning")
    mocker.patch("trxo.utils.imports.sync_handler.success")

    diff_manager = MagicMock()
    diff_manager.perform_diff.return_value = {"removed": [{"_id": "1"}]}
    mocker.patch(
        "trxo.utils.imports.sync_handler.DiffManager", return_value=diff_manager
    )

    deletion_manager = MagicMock()
    deletion_manager.get_items_to_delete.return_value = [{"_id": "1"}]
    deletion_manager.confirm_deletions.return_value = True
    deletion_manager.execute_deletions.return_value = {"deleted": 1}
    mocker.patch(
        "trxo.utils.imports.sync_handler.DeletionManager", return_value=deletion_manager
    )

    result = SyncHandler.handle_sync_deletions(
        command_name="scripts",
        item_type="scripts",
        delete_func=MagicMock(),
        token="t",
        base_url="url",
        force=True,
    )

    deletion_manager.execute_deletions.assert_called_once()
    deletion_manager.print_summary.assert_called_once()
    assert result == {"deleted": 1}


def test_handle_sync_deletions_passes_all_args(mocker):
    """Verify that all onprem / IDM / am_base_url args are forwarded to DiffManager."""
    mocker.patch("trxo.utils.imports.sync_handler.info")
    mocker.patch("trxo.utils.imports.sync_handler.warning")
    mocker.patch("trxo.utils.imports.sync_handler.success")

    diff_manager = MagicMock()
    diff_manager.perform_diff.return_value = {"removed": [{"_id": "1"}]}
    mocker.patch(
        "trxo.utils.imports.sync_handler.DiffManager", return_value=diff_manager
    )

    deletion_manager = MagicMock()
    deletion_manager.get_items_to_delete.return_value = [{"_id": "1"}]
    deletion_manager.confirm_deletions.return_value = True
    deletion_manager.execute_deletions.return_value = {"deleted": 1}
    mocker.patch(
        "trxo.utils.imports.sync_handler.DeletionManager", return_value=deletion_manager
    )

    SyncHandler.handle_sync_deletions(
        command_name="services",
        item_type="services",
        delete_func=MagicMock(),
        token="tok",
        base_url="url",
        file_path="f.json",
        realm="alpha",
        jwk_path="jwk",
        sa_id="sid",
        project_name="proj",
        auth_mode="service-account",
        onprem_username="u",
        onprem_password="p",
        onprem_realm="r",
        am_base_url="http://am",
        idm_base_url="http://idm",
        idm_username="idm_user",
        idm_password="idm_pass",
        branch="main",
        force=True,
    )

    diff_manager.perform_diff.assert_called_once_with(
        command_name="services",
        file_path="f.json",
        realm="alpha",
        jwk_path="jwk",
        sa_id="sid",
        base_url="url",
        project_name="proj",
        auth_mode="service-account",
        onprem_username="u",
        onprem_password="p",
        onprem_realm="r",
        idm_base_url="http://idm",
        idm_username="idm_user",
        idm_password="idm_pass",
        am_base_url="http://am",
        branch="main",
        generate_html=False,
    )
