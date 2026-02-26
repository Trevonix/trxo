import json
import pytest
import typer

from trxo.commands.imports.base_importer import BaseImporter, SimpleImporter


class DummyImporter(BaseImporter):
    def get_required_fields(self):
        return ["_id"]

    def get_item_type(self):
        return "dummy"

    def get_api_endpoint(self, item_id, base_url):
        return "url"

    def update_item(self, item_data, token, base_url):
        return True


def test_get_storage_mode_default(mocker):
    importer = DummyImporter()
    mocker.patch.object(importer.config_store, "get_current_project", return_value=None)

    assert importer._get_storage_mode() == "local"


def test_get_storage_mode_exception(mocker):
    importer = DummyImporter()
    mocker.patch.object(
        importer.config_store, "get_current_project", side_effect=Exception()
    )

    assert importer._get_storage_mode() == "local"


def test_validate_items_ok():
    importer = DummyImporter()
    importer._validate_items([{"_id": "1"}])


def test_validate_items_missing_field():
    importer = DummyImporter()
    with pytest.raises(ValueError):
        importer._validate_items([{"x": 1}])


def test_validate_items_not_dict():
    importer = DummyImporter()
    with pytest.raises(ValueError):
        importer._validate_items(["bad"])


def test_get_item_identifier():
    importer = DummyImporter()
    assert importer._get_item_identifier({"_id": "a"}) == "a"
    assert importer._get_item_identifier({"id": "b"}) == "b"
    assert importer._get_item_identifier({"name": "c"}) == "c"
    assert importer._get_item_identifier({"x": 1}) is None
    assert importer._get_item_identifier("x") is None


def test_validate_import_hash_calls_hash_manager(mocker):
    importer = DummyImporter()
    mocker.patch.object(
        importer.hash_manager, "validate_import_hash", return_value=True
    )

    assert importer.validate_import_hash([{"_id": "1"}], False) is True


def test_import_from_file_local_success(mocker, tmp_path):
    """Local-mode happy path: hash passes, process_items is called."""
    importer = DummyImporter()

    # Write a real temp file so _import_from_local can open it
    data_file = tmp_path / "data.json"
    data_file.write_text(json.dumps([{"_id": "1"}]))

    mocker.patch.object(importer, "initialize_auth", return_value=("t", "url"))
    mocker.patch.object(importer, "_get_storage_mode", return_value="local")
    mocker.patch.object(importer, "load_data_from_file", return_value=[{"_id": "1"}])
    mocker.patch.object(importer, "validate_import_hash", return_value=True)
    mocker.patch.object(importer, "process_items")
    mocker.patch.object(importer, "print_summary")
    mocker.patch.object(importer, "cleanup")

    importer.import_from_file(file_path=str(data_file))

    importer.process_items.assert_called_once()


def test_import_from_file_missing_file_path(mocker):
    importer = DummyImporter()

    mocker.patch.object(importer, "initialize_auth", return_value=("t", "url"))
    mocker.patch.object(importer, "_get_storage_mode", return_value="local")

    with pytest.raises(typer.Exit):
        importer.import_from_file(file_path=None)


def test_import_from_file_diff_mode(mocker):
    importer = DummyImporter()

    mocker.patch.object(importer, "initialize_auth", return_value=("t", "url"))
    mocker.patch.object(importer, "_perform_diff_analysis")
    mocker.patch.object(importer, "cleanup")

    importer.import_from_file(file_path="f", diff=True)

    importer._perform_diff_analysis.assert_called_once()


def test_apply_cherry_pick_invalid(mocker):
    importer = DummyImporter()

    mocker.patch.object(
        importer.cherry_pick_filter, "validate_cherry_pick_argument", return_value=False
    )

    with pytest.raises(typer.Exit):
        importer._apply_cherry_pick_filter([{"_id": "1"}], "bad")


def test_apply_cherry_pick_empty_result(mocker):
    importer = DummyImporter()

    mocker.patch.object(
        importer.cherry_pick_filter, "validate_cherry_pick_argument", return_value=True
    )
    mocker.patch.object(importer.cherry_pick_filter, "apply_filter", return_value=[])

    result = importer._apply_cherry_pick_filter([{"_id": "1"}], "1")

    assert result == []


def test_process_items_success(mocker):
    importer = DummyImporter()

    mocker.patch.object(importer, "update_item", return_value=True)

    importer.process_items([{"_id": "1"}], "t", "u")

    assert importer.successful_updates == 1
    assert importer.failed_updates == 0


def test_process_items_failure_no_rollback(mocker):
    importer = DummyImporter()

    mocker.patch.object(importer, "update_item", return_value=False)

    importer.process_items([{"_id": "1"}], "t", "u")

    assert importer.failed_updates == 1


def test_process_items_failure_with_rollback(mocker):
    importer = DummyImporter()
    rollback_mgr = mocker.Mock()
    rollback_mgr.baseline_snapshot = {}

    mocker.patch.object(importer, "update_item", return_value=False)
    mocker.patch.object(
        importer, "_execute_rollback_and_exit", side_effect=typer.Exit(1)
    )

    with pytest.raises(typer.Exit):
        importer.process_items(
            [{"_id": "1"}],
            "t",
            "u",
            rollback_manager=rollback_mgr,
            rollback_on_failure=True,
        )


def test_handle_sync_deletions_passthrough(mocker):
    importer = DummyImporter()
    mocker.patch.object(
        importer.sync_handler, "handle_sync_deletions", return_value={"ok": True}
    )

    result = importer._handle_sync_deletions("t", "u")

    assert result == {"ok": True}


def test_simple_importer_smoke():
    importer = SimpleImporter()

    assert importer.get_required_fields() == []
    assert importer.get_item_type() == "items"
    assert importer.get_api_endpoint("1", "u") == "u/dummy"
    assert importer.update_item({}, "t", "u") is True
    assert importer.delete_item("1", "t", "u") is True
