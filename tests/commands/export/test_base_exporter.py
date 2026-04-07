import pytest
import typer

from trxo_lib.operations.export.base_exporter import BaseExporter


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
        "trxo_lib.operations.export.base_exporter.MetadataBuilder.build_metadata",
        return_value={"m": 1},
    )
    return be


def test_export_data_headers_none_path(exporter):
    exporter.export_data(
        command_name="test",
        api_endpoint="/endpoint",
        headers=None,
        view=False,
    )

    exporter.make_http_request.assert_called_once()


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
        "trxo_lib.operations.export.base_exporter.PaginationHandler.is_paginated",
        return_value=True,
    )
    mocker.patch(
        "trxo_lib.operations.export.base_exporter.PaginationHandler.fetch_all_pages",
        return_value={"items": []},
    )

    out = exporter._handle_pagination({"page": 1}, "/e", {}, "https://api")

    assert out == {"items": []}


def test_handle_pagination_failure_fallback(exporter, mocker):
    mocker.patch(
        "trxo_lib.operations.export.base_exporter.PaginationHandler.is_paginated",
        return_value=True,
    )
    mocker.patch(
        "trxo_lib.operations.export.base_exporter.PaginationHandler.fetch_all_pages",
        side_effect=Exception("boom"),
    )

    raw = {"page": 1}
    out = exporter._handle_pagination(raw, "/e", {}, "https://api")

    assert out == raw


def test_remove_rev_fields_recursive(exporter):
    data = {"_rev": "1", "a": {"_rev": "2", "b": [{"_rev": "3", "c": 1}]}}

    cleaned = exporter.remove_rev_fields(data)

    assert "_rev" not in cleaned
    assert "_rev" not in cleaned["a"]
    assert "_rev" not in cleaned["a"]["b"][0]
