import pytest
from trxo.constants import DEFAULT_REALM
from trxo.commands.export.applications import create_applications_export_command


@pytest.fixture
def mock_exporter(mocker):
    exporter = mocker.Mock()
    mocker.patch(
        "trxo.commands.export.applications.BaseExporter",
        return_value=exporter,
    )
    return exporter


def test_export_applications_defaults(mock_exporter):
    export_applications = create_applications_export_command()

    export_applications(
        realm=DEFAULT_REALM,
        view=False,
        view_columns=None,
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
    )

    kwargs = mock_exporter.export_data.call_args.kwargs

    assert kwargs["command_name"] == "applications"
    assert kwargs["view"] is False
    assert kwargs["view_columns"] is None
    assert kwargs["version"] is None
    assert kwargs["no_version"] is False
    assert kwargs["branch"] is None
    assert kwargs["commit_message"] is None
    assert kwargs["jwk_path"] is None
    assert kwargs["client_id"] is None
    assert kwargs["sa_id"] is None
    assert kwargs["base_url"] is None
    assert kwargs["project_name"] is None
    assert kwargs["output_dir"] is None
    assert kwargs["output_file"] is None
    assert kwargs["auth_mode"] is None
    assert kwargs["onprem_username"] is None
    assert kwargs["onprem_password"] is None
    assert kwargs["onprem_realm"] == "root"
    assert f"/openidm/managed/{DEFAULT_REALM}_application" in kwargs["api_endpoint"]


def test_export_applications_custom_values(mock_exporter):
    export_applications = create_applications_export_command()

    export_applications(
        realm="custom",
        view=True,
        view_columns="_id,name",
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
        onprem_realm="custom_root",
    )

    kwargs = mock_exporter.export_data.call_args.kwargs

    assert f"/openidm/managed/custom_application" in kwargs["api_endpoint"]
    assert kwargs["view"] is True
    assert kwargs["view_columns"] == "_id,name"
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
    assert kwargs["onprem_realm"] == "custom_root"
