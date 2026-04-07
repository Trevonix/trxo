from trxo.commands.export.scripts import create_scripts_export_command
from trxo_lib.exports.domains.scripts import decode_script_response
from trxo_lib.exports.service import ExportService
from trxo_lib.constants import DEFAULT_REALM


def test_decode_script_response_decodes_base64(mocker):
    data = {"result": [{"_id": "s1", "script": "cHJpbnQoImhlbGxvIik="}]}

    out = decode_script_response(data)

    assert out["result"][0]["script"] == ['print("hello")']


def test_decode_script_response_handles_invalid_base64(mocker):
    warn = mocker.patch("trxo_lib.exports.domains.scripts.logger.warning")

    data = {"result": [{"_id": "s1", "script": "!!!invalid!!!"}]}

    out = decode_script_response(data)

    assert out["result"][0]["script"] == "!!!invalid!!!"
    warn.assert_called_once()


def test_scripts_export_happy_path(mocker):
    export_scripts = create_scripts_export_command()

    mock_service = mocker.patch.object(ExportService, "export_scripts")

    export_scripts(realm=DEFAULT_REALM, view=False)

    mock_service.assert_called_once()

    _, kwargs = mock_service.call_args

    assert kwargs["realm"] == DEFAULT_REALM
    assert kwargs["view"] is False


def test_scripts_export_view_columns_without_view(mocker):
    export_scripts = create_scripts_export_command()

    mock_service = mocker.patch.object(ExportService, "export_scripts")

    export_scripts(realm=DEFAULT_REALM, view=False, view_columns="_id,name")

    mock_service.assert_called_once()

    _, kwargs = mock_service.call_args
    assert kwargs["view_columns"] == "_id,name"
