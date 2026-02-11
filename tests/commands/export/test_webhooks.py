import pytest
from trxo.commands.export.webhooks import create_webhooks_export_command


def test_export_webhooks_defaults(mocker):
    exporter = mocker.Mock()
    mocker.patch(
        "trxo.commands.export.webhooks.BaseExporter",
        return_value=exporter,
    )

    export_webhooks = create_webhooks_export_command()
    export_webhooks()

    exporter.export_data.assert_called_once()
    kwargs = exporter.export_data.call_args.kwargs

    assert kwargs["command_name"] == "webhooks"
    assert kwargs["api_endpoint"].endswith("/realm-config/webhooks?_queryFilter=true")
    assert "view" in kwargs
    assert "view_columns" in kwargs
    assert "version" in kwargs
    assert "no_version" in kwargs
    assert "branch" in kwargs
    assert "commit_message" in kwargs


def test_export_webhooks_custom_args(mocker):
    exporter = mocker.Mock()
    mocker.patch(
        "trxo.commands.export.webhooks.BaseExporter",
        return_value=exporter,
    )

    export_webhooks = create_webhooks_export_command()
    export_webhooks(
        realm="bravo",
        view=True,
        view_columns="_id,name",
        version="v1",
        no_version=True,
        branch="dev",
        commit="msg",
        jwk_path="k",
        client_id="c",
        sa_id="s",
        base_url="b",
        project_name="p",
        output_dir="d",
        output_file="f",
        auth_mode="onprem",
        onprem_username="u",
        onprem_password="pw",
        onprem_realm="root",
    )

    exporter.export_data.assert_called_once()
    kwargs = exporter.export_data.call_args.kwargs

    assert kwargs["command_name"] == "webhooks"
    assert kwargs["api_endpoint"].endswith("/realms/bravo/realm-config/webhooks?_queryFilter=true")
    assert kwargs["view"] is True
    assert kwargs["view_columns"] == "_id,name"
    assert kwargs["version"] == "v1"
    assert kwargs["no_version"] is True
    assert kwargs["branch"] == "dev"
    assert kwargs["commit_message"] == "msg"
    assert kwargs["jwk_path"] == "k"
    assert kwargs["client_id"] == "c"
    assert kwargs["sa_id"] == "s"
    assert kwargs["base_url"] == "b"
    assert kwargs["project_name"] == "p"
    assert kwargs["output_dir"] == "d"
    assert kwargs["output_file"] == "f"
    assert kwargs["auth_mode"] == "onprem"
    assert kwargs["onprem_username"] == "u"
    assert kwargs["onprem_password"] == "pw"
    assert kwargs["onprem_realm"] == "root"
