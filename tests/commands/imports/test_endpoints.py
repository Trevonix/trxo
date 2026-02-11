import pytest
from trxo.commands.imports.endpoints import (
    EndpointsImporter,
    create_endpoints_import_command,
)


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
    mocker.patch("trxo.commands.imports.endpoints.info")

    data = {"_id": "endpoint/test", "name": "Test"}

    result = importer.update_item(data, "t", "http://x")

    assert result is True
    importer.make_http_request.assert_called_once()


def test_update_item_missing_id(mocker):
    importer = EndpointsImporter()
    mocker.patch("trxo.commands.imports.endpoints.error")

    result = importer.update_item({}, "t", "http://x")

    assert result is False


def test_update_item_http_error(mocker):
    importer = EndpointsImporter()

    importer.make_http_request = mocker.Mock(side_effect=Exception("boom"))
    mocker.patch("trxo.commands.imports.endpoints.error")

    data = {"_id": "endpoint/test"}

    result = importer.update_item(data, "t", "http://x")

    assert result is False
    importer.make_http_request.assert_called_once()


def test_create_endpoints_import_command_calls_import_from_file(mocker):
    importer = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.endpoints.EndpointsImporter",
        return_value=importer,
    )

    import_cmd = create_endpoints_import_command()
    import_cmd(
        cherry_pick="id1,id2",
        force_import=True,
        diff=False,
        branch="main",
        file="x.json",
        jwk_path="jwk",
        client_id="cid",
        sa_id="sid",
        base_url="http://x",
        project_name="proj",
        auth_mode="service-account",
        onprem_username="u",
        onprem_password="p",
        onprem_realm="root",
    )

    importer.import_from_file.assert_called_once()
    kwargs = importer.import_from_file.call_args.kwargs

    assert kwargs["file_path"] == "x.json"
    assert kwargs["force_import"] is True
    assert kwargs["diff"] is False
    assert kwargs["branch"] == "main"
    assert kwargs["cherry_pick"] == "id1,id2"
