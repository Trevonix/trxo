import pytest
from click.exceptions import Exit
from trxo.commands.export.services import (
    create_services_export_command,
    ServicesExporter,
)
from trxo.constants import DEFAULT_REALM


def test_services_export_realm_happy_path(mocker):
    export_services = create_services_export_command()

    mock_exporter = mocker.Mock(spec=ServicesExporter)
    mocker.patch(
        "trxo.commands.export.services.ServicesExporter", return_value=mock_exporter
    )

    mock_exporter.export_data.return_value = None

    export_services(scope="realm", realm=DEFAULT_REALM, view=False)

    mock_exporter.export_data.assert_called_once()

    _, kwargs = mock_exporter.export_data.call_args

    assert kwargs["command_name"] == "services"
    assert DEFAULT_REALM in kwargs["api_endpoint"]
    assert kwargs["view"] is False


def test_services_export_global_happy_path(mocker):
    export_services = create_services_export_command()

    mock_exporter = mocker.Mock(spec=ServicesExporter)
    mocker.patch(
        "trxo.commands.export.services.ServicesExporter", return_value=mock_exporter
    )

    mock_exporter.export_data.return_value = None

    export_services(scope="global", view=False)

    mock_exporter.export_data.assert_called_once()

    _, kwargs = mock_exporter.export_data.call_args

    assert kwargs["command_name"] == "services"
    assert kwargs["api_endpoint"] == "/am/json/global-config/services?_queryFilter=true"
    assert kwargs["view"] is False


def test_services_export_invalid_scope_raises_exit(mocker):
    export_services = create_services_export_command()

    mocker.patch("trxo.commands.export.services.ServicesExporter")
    mocker.patch("trxo.utils.console.error")

    with pytest.raises(Exit):
        export_services(scope="invalid")
