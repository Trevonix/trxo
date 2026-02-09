from trxo.commands.export.realms import create_realms_export_command
from trxo.commands.export.realms import BaseExporter


def test_realms_export_happy_path(mocker):
    export_realms = create_realms_export_command()

    mock_exporter = mocker.Mock(spec=BaseExporter)
    mocker.patch("trxo.commands.export.realms.BaseExporter", return_value=mock_exporter)

    mock_exporter.export_data.return_value = None

    export_realms(view=False)

    mock_exporter.export_data.assert_called_once()

    _, kwargs = mock_exporter.export_data.call_args

    assert kwargs["command_name"] == "realms"
    assert kwargs["api_endpoint"] == "/am/json/global-config/realms?_queryFilter=true"
    assert kwargs["view"] is False


def test_realms_export_view_columns_without_view(mocker):
    export_realms = create_realms_export_command()

    mock_exporter = mocker.Mock(spec=BaseExporter)
    mocker.patch("trxo.commands.export.realms.BaseExporter", return_value=mock_exporter)

    mock_exporter.export_data.return_value = None

    export_realms(view=False, view_columns="_id,name")

    mock_exporter.export_data.assert_called_once()
