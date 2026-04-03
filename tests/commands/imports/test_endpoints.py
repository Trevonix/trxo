import pytest
from trxo.commands.imports.endpoints import create_endpoints_import_command
from trxo_lib.operations.imports.endpoints import EndpointsImporter


def test_endpoints_importer_required_fields():
    importer = EndpointsImporter()
    assert importer.get_required_fields() == ["_id"]


def test_endpoints_importer_item_type():
    importer = EndpointsImporter()
    assert importer.get_item_type() == "custom endpoints"


def test_endpoints_importer_api_endpoint():
    importer = EndpointsImporter()
    url = importer.get_api_endpoint("endpoint/test", "http://x")
    assert url == "http://x/openidm/config/endpoint/test"


def test_update_item_success(mocker):
    importer = EndpointsImporter()

    importer.make_http_request = mocker.Mock()
    mocker.patch("trxo_lib.operations.imports.endpoints.info")

    data = {"_id": "endpoint/test", "name": "Test"}

    result = importer.update_item(data, "t", "http://x")

    assert result is True
    importer.make_http_request.assert_called_once()


def test_update_item_missing_id(mocker):
    importer = EndpointsImporter()
    mocker.patch("trxo_lib.operations.imports.endpoints.error")

    result = importer.update_item({}, "t", "http://x")

    assert result is False


def test_update_item_http_error(mocker):
    importer = EndpointsImporter()

    importer.make_http_request = mocker.Mock(side_effect=Exception("boom"))
    mocker.patch("trxo_lib.operations.imports.endpoints.error")

    data = {"_id": "endpoint/test"}

    result = importer.update_item(data, "t", "http://x")

    assert result is False
    importer.make_http_request.assert_called_once()


def test_create_endpoints_import_command_wires_service(mocker):
    mock_service = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.endpoints.ImportService", return_value=mock_service
    )

    import_cmd = create_endpoints_import_command()
    import_cmd(
        cherry_pick="id1,id2",
        force_import=True,
        diff=False,
        branch="main",
        file="x.json",
    )

    mock_service.import_endpoints.assert_called_once()
    kwargs = mock_service.import_endpoints.call_args.kwargs
    assert kwargs["file"] == "x.json"
    assert kwargs["force_import"] is True
    assert kwargs["cherry_pick"] == "id1,id2"
