import pytest
from trxo.commands.export.realms import create_realms_export_command


def test_realms_export_happy_path(mocker):
    export_realms = create_realms_export_command()

    mock_exporter = mocker.Mock()
    mock_exporter.export_data.return_value.status_code = 200
    mock_exporter.export_data.return_value.data = {}
    mock_exporter.export_data.return_value.metadata = {}
    mocker.patch(
        "trxo_lib.operations.export.realms.BaseExporter", return_value=mock_exporter
    )

    mock_exporter.export_data.return_value = None

    export_realms(view=False)

    mock_exporter.export_data.assert_called_once()

    _, kwargs = mock_exporter.export_data.call_args

    assert kwargs["command_name"] == "realms"
    assert kwargs["api_endpoint"] == "/am/json/global-config/realms?_queryFilter=true"
    assert kwargs["view"] is False


from trxo_lib.exceptions import TrxoAbort


def test_realms_export_view_columns_without_view(mocker):
    export_realms = create_realms_export_command()

    mock_exporter = mocker.Mock()
    mock_exporter.export_data.return_value.status_code = 200
    mock_exporter.export_data.return_value.data = {}
    mock_exporter.export_data.return_value.metadata = {}
    mocker.patch(
        "trxo_lib.operations.export.realms.BaseExporter", return_value=mock_exporter
    )

    mock_exporter.export_data.return_value = None

    with pytest.raises(TrxoAbort):
        export_realms(view=False, view_columns="_id,name")
