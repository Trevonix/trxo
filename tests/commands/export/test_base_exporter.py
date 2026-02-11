import pytest
import typer

from trxo.commands.export.base_exporter import BaseExporter


@pytest.fixture
def exporter(mocker):
    be = BaseExporter()

    be.initialize_auth = mocker.Mock(return_value=("token", "https://api"))
    be.make_http_request = mocker.Mock()
    be.build_auth_headers = mocker.Mock(return_value={"Authorization": "Bearer token"})
    be._construct_api_url = mocker.Mock(return_value="https://api/endpoint")
    be.cleanup = mocker.Mock()
    be.logger = mocker.Mock()
    be.hash_manager = mocker.Mock()
    be.git_handler = mocker.Mock()
    be.config_store = mocker.Mock()

    response = mocker.Mock()
    response.json.return_value = {"data": [{"_rev": "1", "x": 1}]}
    response.status_code = 200
    be.make_http_request.return_value = response

    mocker.patch(
        "trxo.commands.export.base_exporter.MetadataBuilder.build_metadata",
        return_value={"m": 1},
    )
    mocker.patch(
        "trxo.commands.export.base_exporter.ViewRenderer.display_table_view"
    )
    mocker.patch(
        "trxo.commands.export.base_exporter.PaginationHandler.is_paginated",
        return_value=False,
    )
    mocker.patch(
        "trxo.commands.export.base_exporter.FileSaver.save_to_local",
        return_value="file.json",
    )
    mocker.patch("trxo.commands.export.base_exporter.success")
    mocker.patch("trxo.commands.export.base_exporter.error")
    mocker.patch("trxo.commands.export.base_exporter.info")

    return be


def test_export_data_headers_none_path(exporter):
    exporter.export_data(
        command_name="test",
        api_endpoint="/endpoint",
        headers=None,
        view=False,
    )

    exporter.make_http_request.assert_called_once()


def test_export_data_view_mode(exporter):
    exporter.export_data(
        command_name="test",
        api_endpoint="/endpoint",
        headers={},
        view=True,
        view_columns="_id",
    )


def test_export_data_view_columns_without_view_warns(exporter, mocker):
    warn = mocker.patch("trxo.commands.export.base_exporter.warning")

    exporter.export_data(
        command_name="test",
        api_endpoint="/endpoint",
        headers={},
        view=False,
        view_columns="_id",
    )

    warn.assert_called_once()


def test_export_data_git_storage(exporter, mocker):
    exporter._get_storage_mode = mocker.Mock(return_value="git")
    exporter.git_handler.save_to_git = mocker.Mock(return_value="git.json")

    exporter.export_data(
        command_name="test",
        api_endpoint="/endpoint",
        headers={},
        view=False,
    )

    exporter.git_handler.save_to_git.assert_called_once()


def test_export_data_non_200_response(exporter):
    exporter.make_http_request.return_value.status_code = 400
    exporter.make_http_request.return_value.text = "bad"

    exporter.export_data(
        command_name="test",
        api_endpoint="/endpoint",
        headers={},
        view=False,
    )


def test_handle_pagination_success(exporter, mocker):
    mocker.patch(
        "trxo.commands.export.base_exporter.PaginationHandler.is_paginated",
        return_value=True,
    )
    mocker.patch(
        "trxo.commands.export.base_exporter.PaginationHandler.fetch_all_pages",
        return_value={"items": []},
    )

    out = exporter._handle_pagination({"page": 1}, "/e", {}, "https://api")

    assert out == {"items": []}


def test_handle_pagination_failure_fallback(exporter, mocker):
    mocker.patch(
        "trxo.commands.export.base_exporter.PaginationHandler.is_paginated",
        return_value=True,
    )
    mocker.patch(
        "trxo.commands.export.base_exporter.PaginationHandler.fetch_all_pages",
        side_effect=Exception("boom"),
    )

    raw = {"page": 1}
    out = exporter._handle_pagination(raw, "/e", {}, "https://api")

    assert out == raw


def test_get_storage_mode_exception_defaults_local(exporter, mocker):
    exporter.config_store.get_current_project.side_effect = Exception("boom")

    assert exporter._get_storage_mode() == "local"


def test_save_response_git_path(exporter, mocker):
    exporter._get_storage_mode = mocker.Mock(return_value="git")
    exporter.git_handler.save_to_git = mocker.Mock(return_value="git.json")

    path = exporter.save_response({}, "cmd", branch="b", commit_message="m")

    assert path == "git.json"


def test_save_response_local_path(exporter):
    exporter._get_storage_mode = lambda: "local"
    path = exporter.save_response({}, "cmd", output_dir="d")

    assert path == "file.json"


def test_remove_rev_fields_recursive(exporter):
    data = {"_rev": "1", "a": {"_rev": "2", "b": [{"_rev": "3", "c": 1}]}}

    cleaned = exporter.remove_rev_fields(data)

    assert "_rev" not in cleaned
    assert "_rev" not in cleaned["a"]
    assert "_rev" not in cleaned["a"]["b"][0]
