import pytest

from trxo.commands.export.privileges import create_privileges_export_command


@pytest.fixture
def mock_exporter(mocker):
    exporter = mocker.Mock()
    mocker.patch(
        "trxo.commands.export.privileges.BaseExporter",
        return_value=exporter,
    )
    return exporter


def _call_privileges(export_privileges, realm=None, **overrides):
    """Helper to call export_privileges with sensible defaults."""
    defaults = dict(
        realm=realm,
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
    defaults.update(overrides)
    export_privileges(**defaults)


def test_export_privileges_no_realm(mock_exporter):
    export_privileges = create_privileges_export_command()

    _call_privileges(export_privileges, realm=None)

    kwargs = mock_exporter.export_data.call_args.kwargs

    assert kwargs["command_name"] == "privileges"
    assert kwargs["api_endpoint"] == '/openidm/config?_queryFilter=_id co "privilege"'
    assert kwargs["response_filter"] is None
    assert kwargs["view"] is False
    assert kwargs["view_columns"] is None


def test_export_privileges_with_realm_creates_filter(mock_exporter):
    export_privileges = create_privileges_export_command()

    _call_privileges(
        export_privileges,
        realm="alpha",
        view=True,
        view_columns="_id,name",
        version="v1",
        no_version=True,
        branch="main",
        commit="msg",
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

    assert kwargs["command_name"] == "privileges"
    assert callable(kwargs["response_filter"])
    assert kwargs["view"] is True
    assert kwargs["view_columns"] == "_id,name"
    assert kwargs["version"] == "v1"
    assert kwargs["no_version"] is True
    assert kwargs["branch"] == "main"
    assert kwargs["commit_message"] == "msg"


def test_privileges_response_filter_keeps_only_realm_ids(mock_exporter):
    export_privileges = create_privileges_export_command()

    _call_privileges(export_privileges, realm="alpha")

    response_filter = mock_exporter.export_data.call_args.kwargs["response_filter"]

    raw = {
        "result": [
            {"_id": "alphaOrgPrivileges", "x": 1},
            {"_id": "privilegeAssignments", "x": 2},
            {"_id": "otherPrivilege", "x": 3},
            {"_id": "betaOrgPrivileges", "x": 4},
        ]
    }

    filtered = response_filter(raw)

    assert len(filtered["result"]) == 2
    ids = {item["_id"] for item in filtered["result"]}
    assert ids == {"alphaOrgPrivileges", "privilegeAssignments"}


def test_privileges_response_filter_non_matching_shape_returns_raw(mock_exporter):
    export_privileges = create_privileges_export_command()

    _call_privileges(export_privileges, realm="alpha")

    response_filter = mock_exporter.export_data.call_args.kwargs["response_filter"]

    raw = {"not_result": 123}
    filtered = response_filter(raw)

    assert filtered == raw
