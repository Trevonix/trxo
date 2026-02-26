import pytest
import typer

from trxo.commands.export.agents import (
    create_agents_export_command,
    create_agents_callback,
)


@pytest.fixture
def mock_exporter(mocker):
    exporter = mocker.Mock()
    mocker.patch("trxo.commands.export.agents.BaseExporter", return_value=exporter)
    return exporter


@pytest.fixture
def mock_console(mocker):
    mocker.patch("trxo.commands.export.agents.console")
    mocker.patch("trxo.commands.export.agents.warning")
    mocker.patch("trxo.commands.export.agents.info")
    return mocker


def test_export_gateway_agents_defaults(mock_exporter):
    export_gateway, _, _ = create_agents_export_command()

    export_gateway()

    mock_exporter.export_data.assert_called_once()
    kwargs = mock_exporter.export_data.call_args.kwargs
    assert kwargs["command_name"] == "agents_gateway"
    assert "/IdentityGatewayAgent?_queryFilter=true" in kwargs["api_endpoint"]


def test_export_gateway_agents_custom_args(mock_exporter):
    export_gateway, _, _ = create_agents_export_command()

    export_gateway(
        realm="custom",
        view=True,
        view_columns="_id,name",
        jwk_path="jwk.json",
        sa_id="sid",
        base_url="https://example.com",
        project_name="proj",
        output_dir="out",
        output_file="file",
        auth_mode="service-account",
        onprem_username="user",
        onprem_password="pass",
        onprem_realm="root",
        am_base_url="http://am",
        version="v1",
        no_version=True,
        branch="main",
        commit="msg",
    )

    kwargs = mock_exporter.export_data.call_args.kwargs
    assert "custom" in kwargs["api_endpoint"]
    assert kwargs["view"] is True
    assert kwargs["view_columns"] == "_id,name"
    assert kwargs["jwk_path"] == "jwk.json"
    assert kwargs["sa_id"] == "sid"
    assert kwargs["base_url"] == "https://example.com"
    assert kwargs["project_name"] == "proj"
    assert kwargs["output_dir"] == "out"
    assert kwargs["output_file"] == "file"
    assert kwargs["auth_mode"] == "service-account"
    assert kwargs["onprem_username"] == "user"
    assert kwargs["onprem_password"] == "pass"
    assert kwargs["onprem_realm"] == "root"
    assert kwargs["version"] == "v1"
    assert kwargs["no_version"] is True
    assert kwargs["branch"] == "main"
    assert kwargs["commit_message"] == "msg"


def test_export_java_agents_defaults(mock_exporter):
    _, export_java, _ = create_agents_export_command()

    export_java()

    mock_exporter.export_data.assert_called_once()
    kwargs = mock_exporter.export_data.call_args.kwargs
    assert kwargs["command_name"] == "agents_java"
    assert "/J2EEAgent?_queryFilter=true" in kwargs["api_endpoint"]


def test_export_web_agents_defaults(mock_exporter):
    _, _, export_web = create_agents_export_command()

    export_web()

    mock_exporter.export_data.assert_called_once()
    kwargs = mock_exporter.export_data.call_args.kwargs
    assert kwargs["command_name"] == "agents_web"
    assert "/WebAgent?_queryFilter=true" in kwargs["api_endpoint"]


def test_agents_callback_no_subcommand_exits(mock_console, mocker):
    callback = create_agents_callback()

    ctx = mocker.Mock()
    ctx.invoked_subcommand = None

    with pytest.raises(typer.Exit):
        callback(ctx)


def test_agents_callback_with_subcommand_no_exit(mock_console, mocker):
    callback = create_agents_callback()

    ctx = mocker.Mock()
    ctx.invoked_subcommand = "gateway"

    callback(ctx)
