from trxo.commands.export.authn import create_authn_export_command
from trxo.constants import DEFAULT_REALM


def test_authn_export_calls_exporter(mocker):
    mock_exporter = mocker.Mock()
    mocker.patch("trxo.commands.export.authn.BaseExporter", return_value=mock_exporter)

    export_authn = create_authn_export_command()

    export_authn(
        realm="alpha",
        view=True,
        view_columns="_id,name",
        jwk_path="key.jwk",
        sa_id="sid",
        base_url="https://example.com",
        project_name="proj",
        output_dir="out",
        output_file="file",
        auth_mode="service-account",
        onprem_username=None,
        onprem_password=None,
        onprem_realm="root",
        am_base_url=None,
        version="v1",
        no_version=False,
        branch="main",
        commit="msg",
    )

    mock_exporter.export_data.assert_called_once()

    args, kwargs = mock_exporter.export_data.call_args

    assert kwargs["command_name"] == "authn"
    assert kwargs["headers"]["Content-Type"] == "application/json"
    assert kwargs["headers"]["Accept-API-Version"] == "protocol=2.0,resource=1.0"
    assert (
        "/am/json/realms/root/realms/alpha/realm-config/authentication"
        in kwargs["api_endpoint"]
    )


def test_authn_export_default_realm(mocker):
    mock_exporter = mocker.Mock()
    mocker.patch("trxo.commands.export.authn.BaseExporter", return_value=mock_exporter)

    export_authn = create_authn_export_command()

    export_authn(realm=DEFAULT_REALM)

    args, kwargs = mock_exporter.export_data.call_args

    assert (
        f"/realms/{DEFAULT_REALM}/realm-config/authentication" in kwargs["api_endpoint"]
    )
