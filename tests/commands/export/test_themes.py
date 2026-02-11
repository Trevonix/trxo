import pytest
from trxo.commands.export.themes import create_themes_export_command


def test_export_themes_with_realm(mocker):
    exporter = mocker.Mock()
    mocker.patch(
        "trxo.commands.export.themes.BaseExporter",
        return_value=exporter,
    )

    export_themes = create_themes_export_command()
    export_themes(realm="alpha")

    exporter.export_data.assert_called_once()
    kwargs = exporter.export_data.call_args.kwargs

    assert (
        kwargs["api_endpoint"]
        == "/openidm/config/ui/themerealm?_fields=realm/alpha"
    )
