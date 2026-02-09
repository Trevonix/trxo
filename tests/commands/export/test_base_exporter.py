import pytest
import typer
from trxo.commands.export.base_exporter import BaseExporter


def test_export_data_success_view_mode(mocker):
    exporter = BaseExporter()

    # Mock internals
    mocker.patch.object(
        exporter, "initialize_auth", return_value=("token", "https://base")
    )
    mocker.patch.object(
        exporter, "build_auth_headers", return_value={"Authorization": "Bearer token"}
    )
    mocker.patch.object(exporter, "_construct_api_url", return_value="https://base/api")
    mocker.patch.object(exporter, "make_http_request")
    mocker.patch.object(exporter, "_handle_pagination", return_value={"data": []})
    mocker.patch.object(exporter, "remove_rev_fields", return_value={"data": []})
    mocker.patch(
        "trxo.commands.export.base_exporter.MetadataBuilder.build_metadata",
        return_value={"meta": "x"},
    )
    mocker.patch("trxo.commands.export.base_exporter.ViewRenderer.display_table_view")
    mocker.patch.object(exporter, "cleanup")

    exporter.make_http_request.return_value.json.return_value = {"data": []}
    exporter.make_http_request.return_value.status_code = 200

    exporter.export_data(
        command_name="authn",
        api_endpoint="/test",
        headers={"Content-Type": "application/json"},
        view=True,
    )

    exporter.make_http_request.assert_called_once()
    exporter.cleanup.assert_called_once()
    exporter.initialize_auth.assert_called_once()


def test_export_data_success_save_mode_local(mocker):
    exporter = BaseExporter()

    mocker.patch.object(
        exporter, "initialize_auth", return_value=("token", "https://base")
    )
    mocker.patch.object(
        exporter, "build_auth_headers", return_value={"Authorization": "Bearer token"}
    )
    mocker.patch.object(exporter, "_construct_api_url", return_value="https://base/api")
    mocker.patch.object(exporter, "make_http_request")
    mocker.patch.object(exporter, "_handle_pagination", return_value={"data": []})
    mocker.patch.object(exporter, "remove_rev_fields", return_value={"data": []})
    mocker.patch.object(exporter, "_get_storage_mode", return_value="local")
    mocker.patch.object(exporter.hash_manager, "create_hash", return_value="hash")
    mocker.patch.object(exporter.hash_manager, "save_export_hash")
    mocker.patch.object(exporter, "save_response", return_value="file.json")
    mocker.patch(
        "trxo.commands.export.base_exporter.MetadataBuilder.build_metadata",
        return_value={"meta": "x"},
    )
    mocker.patch.object(exporter, "cleanup")

    exporter.make_http_request.return_value.json.return_value = {"data": []}
    exporter.make_http_request.return_value.status_code = 200

    exporter.export_data(
        command_name="authn",
        api_endpoint="/test",
        headers={"Content-Type": "application/json"},
        view=False,
        output_dir="out",
        output_file="file",
    )

    exporter.save_response.assert_called_once()
    exporter.hash_manager.create_hash.assert_called_once()
    exporter.hash_manager.save_export_hash.assert_called_once()
    exporter.cleanup.assert_called_once()


def test_export_data_view_columns_without_view_warns_and_returns(mocker):
    exporter = BaseExporter()

    warn_spy = mocker.patch("trxo.commands.export.base_exporter.warning")

    mocker.patch.object(
        exporter, "initialize_auth", return_value=("token", "https://base")
    )
    mocker.patch.object(
        exporter, "build_auth_headers", return_value={"Authorization": "Bearer token"}
    )
    mocker.patch.object(exporter, "_construct_api_url", return_value="https://base/api")
    mocker.patch.object(exporter, "make_http_request")
    mocker.patch.object(exporter, "_handle_pagination", return_value={"data": []})
    mocker.patch.object(exporter, "remove_rev_fields", return_value={"data": []})
    mocker.patch(
        "trxo.commands.export.base_exporter.MetadataBuilder.build_metadata",
        return_value={"meta": "x"},
    )
    mocker.patch.object(exporter, "cleanup")

    exporter.make_http_request.return_value.json.return_value = {"data": []}
    exporter.make_http_request.return_value.status_code = 200

    exporter.export_data(
        command_name="authn",
        api_endpoint="/test",
        headers={},
        view=False,
        view_columns="_id,name",
    )

    warn_spy.assert_called_once()
    exporter.cleanup.assert_called_once()


def test_export_data_http_error_raises_exit(mocker):
    exporter = BaseExporter()

    mocker.patch.object(
        exporter, "initialize_auth", return_value=("token", "https://base")
    )
    mocker.patch.object(
        exporter, "build_auth_headers", return_value={"Authorization": "Bearer token"}
    )
    mocker.patch.object(exporter, "_construct_api_url", return_value="https://base/api")
    mocker.patch.object(exporter, "make_http_request", side_effect=Exception("boom"))
    mocker.patch.object(exporter, "cleanup")
    mocker.patch("trxo.commands.export.base_exporter.error")

    with pytest.raises(typer.Exit):
        exporter.export_data(
            command_name="authn",
            api_endpoint="/test",
            headers={"Content-Type": "application/json"},
        )

    exporter.cleanup.assert_called_once()


def test_remove_rev_fields_nested():
    exporter = BaseExporter()

    data = {
        "_rev": "123",
        "a": 1,
        "b": {"_rev": "456", "x": 2},
        "c": [{"_rev": "789", "y": 3}],
    }

    cleaned = exporter.remove_rev_fields(data)

    assert "_rev" not in cleaned
    assert "_rev" not in cleaned["b"]
    assert "_rev" not in cleaned["c"][0]
    assert cleaned["b"]["x"] == 2
    assert cleaned["c"][0]["y"] == 3


def test_get_current_auth():
    exporter = BaseExporter()
    exporter._current_token = "t"
    exporter._current_api_base_url = "u"

    token, url = exporter.get_current_auth()

    assert token == "t"
    assert url == "u"
