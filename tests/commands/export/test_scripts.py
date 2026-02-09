import pytest
from trxo.commands.export.scripts import (
    create_scripts_export_command,
    decode_script_response,
)
from trxo.commands.export.scripts import BaseExporter
from trxo.constants import DEFAULT_REALM


def test_decode_script_response_decodes_base64(mocker):
    data = {"result": [{"_id": "s1", "script": "cHJpbnQoImhlbGxvIik="}]}

    out = decode_script_response(data)

    assert out["result"][0]["script"] == ['print("hello")']


def test_decode_script_response_handles_invalid_base64(mocker):
    warn = mocker.patch("trxo.commands.export.scripts.warning")

    data = {"result": [{"_id": "s1", "script": "!!!invalid!!!"}]}

    out = decode_script_response(data)

    assert out["result"][0]["script"] == "!!!invalid!!!"
    warn.assert_called_once()


def test_scripts_export_happy_path(mocker):
    export_scripts = create_scripts_export_command()

    mock_exporter = mocker.Mock(spec=BaseExporter)
    mocker.patch(
        "trxo.commands.export.scripts.BaseExporter", return_value=mock_exporter
    )

    mock_exporter.export_data.return_value = None

    export_scripts(realm=DEFAULT_REALM, view=False)

    mock_exporter.export_data.assert_called_once()

    _, kwargs = mock_exporter.export_data.call_args

    assert kwargs["command_name"] == "scripts"
    assert DEFAULT_REALM in kwargs["api_endpoint"]
    assert kwargs["response_filter"] == decode_script_response


def test_scripts_export_view_columns_without_view(mocker):
    export_scripts = create_scripts_export_command()

    mock_exporter = mocker.Mock(spec=BaseExporter)
    mocker.patch(
        "trxo.commands.export.scripts.BaseExporter", return_value=mock_exporter
    )

    mock_exporter.export_data.return_value = None

    export_scripts(realm=DEFAULT_REALM, view=False, view_columns="_id,name")

    mock_exporter.export_data.assert_called_once()
