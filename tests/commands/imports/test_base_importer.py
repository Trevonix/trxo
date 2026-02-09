import pytest
from click.exceptions import Exit
from trxo.commands.imports.base_importer import BaseImporter, SimpleImporter


def test_import_from_file_local_happy_path(mocker):
    importer = SimpleImporter()

    mocker.patch.object(
        importer, "initialize_auth", return_value=("token", "https://base")
    )
    mocker.patch.object(importer, "_get_storage_mode", return_value="local")
    mocker.patch.object(importer, "_import_from_local", return_value=[{"_id": "1"}])
    mocker.patch.object(importer, "process_items")
    mocker.patch.object(importer, "print_summary")
    mocker.patch.object(importer, "cleanup")

    importer.import_from_file(file_path="data.json")

    importer._import_from_local.assert_called_once_with("data.json", False)
    importer.process_items.assert_called_once()
    importer.print_summary.assert_called_once()
    importer.cleanup.assert_called_once()


def test_import_from_file_missing_path_raises_exit(mocker):
    importer = SimpleImporter()

    mocker.patch.object(
        importer, "initialize_auth", return_value=("token", "https://base")
    )
    mocker.patch.object(importer, "_get_storage_mode", return_value="local")
    mocker.patch("trxo.utils.console.error")

    with pytest.raises(Exit):
        importer.import_from_file()


def test_import_from_file_git_happy_path(mocker):
    importer = SimpleImporter()

    mocker.patch.object(
        importer, "initialize_auth", return_value=("token", "https://base")
    )
    mocker.patch.object(importer, "_get_storage_mode", return_value="git")
    mocker.patch.object(importer, "_import_from_git", return_value=[{"_id": "1"}])
    mocker.patch.object(importer, "process_items")
    mocker.patch.object(importer, "print_summary")
    mocker.patch.object(importer, "cleanup")

    importer.import_from_file()

    importer._import_from_git.assert_called_once()
    importer.process_items.assert_called_once()
    importer.print_summary.assert_called_once()
    importer.cleanup.assert_called_once()


def test_import_from_file_no_items_returns(mocker):
    importer = SimpleImporter()

    mocker.patch.object(
        importer, "initialize_auth", return_value=("token", "https://base")
    )
    mocker.patch.object(importer, "_get_storage_mode", return_value="local")
    mocker.patch.object(importer, "_import_from_local", return_value=[])
    mocker.patch("trxo.utils.console.warning")
    mocker.patch.object(importer, "cleanup")

    importer.import_from_file(file_path="data.json")

    importer.cleanup.assert_called_once()


def test_process_items_all_success(mocker):
    importer = SimpleImporter()

    mocker.patch.object(importer, "update_item", return_value=True)
    mocker.patch.object(importer, "_get_item_identifier", return_value="1")

    importer.process_items(
        items=[{"_id": "1"}, {"_id": "2"}],
        token="token",
        base_url="https://base",
    )

    assert importer.successful_updates == 2
    assert importer.failed_updates == 0


def test_process_items_failure_no_rollback(mocker):
    importer = SimpleImporter()

    mocker.patch.object(importer, "update_item", return_value=False)
    mocker.patch.object(importer, "_get_item_identifier", return_value="1")

    importer.process_items(
        items=[{"_id": "1"}],
        token="token",
        base_url="https://base",
    )

    assert importer.successful_updates == 0
    assert importer.failed_updates == 1


def test_process_items_failure_with_rollback_exit(mocker):
    importer = SimpleImporter()

    rollback_manager = mocker.Mock()
    rollback_manager.baseline_snapshot = {"1": {}}
    rollback_manager.execute_rollback.return_value = {"rolled_back": [], "errors": []}

    mocker.patch.object(importer, "update_item", return_value=False)
    mocker.patch.object(importer, "_get_item_identifier", return_value="1")
    mocker.patch.object(importer, "_print_rollback_report")

    with pytest.raises(Exit):
        importer.process_items(
            items=[{"_id": "1"}],
            token="token",
            base_url="https://base",
            rollback_manager=rollback_manager,
            rollback_on_failure=True,
        )
