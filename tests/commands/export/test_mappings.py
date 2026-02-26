import pytest

from trxo.commands.export.mappings import create_mappings_export_command


@pytest.fixture
def mock_exporter(mocker):
    exporter = mocker.Mock()
    mocker.patch(
        "trxo.commands.export.mappings.BaseExporter",
        return_value=exporter,
    )
    return exporter


def test_export_mappings_defaults(mock_exporter):
    export_mappings = create_mappings_export_command()

    export_mappings(
        view=False,
        view_columns=None,
        version=None,
        no_version=False,
        branch=None,
        commit=None,
        jwk_path=None,
        sa_id=None,
        base_url=None,
        project_name=None,
        output_dir=None,
        output_file=None,
        auth_mode=None,
        onprem_username=None,
        onprem_password=None,
        onprem_realm="root",
        am_base_url=None,
        idm_base_url=None,
        idm_username=None,
        idm_password=None,
    )

    kwargs = mock_exporter.export_data.call_args.kwargs

    assert kwargs["command_name"] == "mappings"
    assert kwargs["api_endpoint"] == "/openidm/config/sync"
    assert kwargs["view"] is False
    assert kwargs["view_columns"] is None
    assert kwargs["version"] is None
    assert kwargs["no_version"] is False
    assert kwargs["branch"] is None
    assert kwargs["commit_message"] is None


def test_export_mappings_all_args(mock_exporter):
    export_mappings = create_mappings_export_command()

    export_mappings(
        view=True,
        view_columns="name,displayName,source,target",
        version="v1",
        no_version=True,
        branch="main",
        commit="commit msg",
        jwk_path="jwk.json",
        sa_id="sid",
        base_url="https://example.com",
        project_name="proj",
        output_dir="out",
        output_file="file",
        auth_mode="service-account",
        onprem_username="user",
        onprem_password="pass",
        onprem_realm="custom",
        am_base_url="http://am",
        idm_base_url="http://idm",
        idm_username="idm_user",
        idm_password="idm_pass",
    )

    kwargs = mock_exporter.export_data.call_args.kwargs

    assert kwargs["view"] is True
    assert kwargs["view_columns"] == "name,displayName,source,target"
    assert kwargs["version"] == "v1"
    assert kwargs["no_version"] is True
    assert kwargs["branch"] == "main"
    assert kwargs["commit_message"] == "commit msg"
    assert kwargs["jwk_path"] == "jwk.json"
    assert kwargs["sa_id"] == "sid"
    assert kwargs["base_url"] == "https://example.com"
    assert kwargs["project_name"] == "proj"
    assert kwargs["output_dir"] == "out"
    assert kwargs["output_file"] == "file"
    assert kwargs["auth_mode"] == "service-account"
    assert kwargs["onprem_username"] == "user"
    assert kwargs["onprem_password"] == "pass"
    assert kwargs["onprem_realm"] == "custom"
    assert kwargs["am_base_url"] == "http://am"
