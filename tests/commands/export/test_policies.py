import pytest

from trxo.commands.export.policies import create_policies_export_command
from trxo.constants import DEFAULT_REALM


@pytest.fixture
def mock_exporter(mocker):
    exporter = mocker.Mock()
    mocker.patch(
        "trxo.commands.export.policies.BaseExporter",
        return_value=exporter,
    )
    return exporter


def test_export_policies_defaults(mock_exporter):
    export_policies = create_policies_export_command()

    export_policies(
        realm=DEFAULT_REALM,
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
    )

    kwargs = mock_exporter.export_data.call_args.kwargs

    assert kwargs["command_name"] == "policies"
    assert (
        kwargs["api_endpoint"]
        == f"/am/json/realms/root/realms/{DEFAULT_REALM}/policies?_queryFilter=true"
    )
    assert kwargs["view"] is False
    assert kwargs["view_columns"] is None
    assert kwargs["version"] is None
    assert kwargs["no_version"] is False
    assert kwargs["branch"] is None
    assert kwargs["commit_message"] is None


def test_export_policies_all_args(mock_exporter):
    export_policies = create_policies_export_command()

    export_policies(
        realm="beta",
        view=True,
        view_columns="_id,name,active",
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
    )

    kwargs = mock_exporter.export_data.call_args.kwargs

    assert (
        kwargs["api_endpoint"]
        == "/am/json/realms/root/realms/beta/policies?_queryFilter=true"
    )
    assert kwargs["view"] is True
    assert kwargs["view_columns"] == "_id,name,active"
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
