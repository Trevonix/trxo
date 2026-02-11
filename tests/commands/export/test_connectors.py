import pytest

from trxo.commands.export.connectors import create_connectors_export_command


@pytest.fixture
def mock_exporter(mocker):
    exporter = mocker.Mock()
    mocker.patch("trxo.commands.export.connectors.BaseExporter", return_value=exporter)
    return exporter


def test_export_connectors_defaults(mock_exporter):
    export_connectors = create_connectors_export_command()

    export_connectors(
        version=None,
        no_version=False,
        branch=None,
        commit=None,
        jwk_path=None,
        client_id=None,
        sa_id=None,
        base_url=None,
        project_name=None,
        output_dir=None,
        output_file=None,
        auth_mode=None,
        onprem_username=None,
        onprem_password=None,
        onprem_realm="root",
        view=False,
        view_columns=None,
    )

    kwargs = mock_exporter.export_data.call_args.kwargs

    assert kwargs["command_name"] == "connectors"
    assert kwargs["api_endpoint"].startswith('/openidm/config?_queryFilter=_id+sw+"provisioner.openicf/"')
    assert kwargs["headers"]["Accept-API-Version"] == "protocol=2.1,resource=1.0"
    assert kwargs["view"] is False
    assert kwargs["view_columns"] is None
    assert kwargs["version"] is None
    assert kwargs["no_version"] is False
    assert kwargs["branch"] is None
    assert kwargs["commit_message"] is None


def test_export_connectors_custom(mock_exporter):
    export_connectors = create_connectors_export_command()

    export_connectors(
        version="v1",
        no_version=True,
        branch="main",
        commit="msg",
        jwk_path="jwk.json",
        client_id="cid",
        sa_id="sid",
        base_url="https://example.com",
        project_name="proj",
        output_dir="out",
        output_file="file",
        auth_mode="service-account",
        onprem_username="user",
        onprem_password="pass",
        onprem_realm="custom",
        view=True,
        view_columns="_id,enabled",
    )

    kwargs = mock_exporter.export_data.call_args.kwargs

    assert kwargs["version"] == "v1"
    assert kwargs["no_version"] is True
    assert kwargs["branch"] == "main"
    assert kwargs["commit_message"] == "msg"
    assert kwargs["jwk_path"] == "jwk.json"
    assert kwargs["client_id"] == "cid"
    assert kwargs["sa_id"] == "sid"
    assert kwargs["base_url"] == "https://example.com"
    assert kwargs["project_name"] == "proj"
    assert kwargs["output_dir"] == "out"
    assert kwargs["output_file"] == "file"
    assert kwargs["auth_mode"] == "service-account"
    assert kwargs["onprem_username"] == "user"
    assert kwargs["onprem_password"] == "pass"
    assert kwargs["onprem_realm"] == "custom"
    assert kwargs["view"] is True
    assert kwargs["view_columns"] == "_id,enabled"
