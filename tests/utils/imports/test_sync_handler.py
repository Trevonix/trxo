from unittest.mock import MagicMock

import pytest

from trxo.utils.imports.sync_handler import SyncHandler


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
        global_policy=False,  # ✅ FIX ADDED
    )
