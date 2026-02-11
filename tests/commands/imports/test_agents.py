import json
import pytest
import typer
from trxo.commands.imports.agents import (
    AgentsImporter,
    create_agents_import_command,
    create_agents_callback,
)


@pytest.fixture
def importer(mocker):
    obj = AgentsImporter("IdentityGatewayAgent", realm="alpha")
    mocker.patch.object(obj, "make_http_request")
    mocker.patch.object(obj, "build_auth_headers", return_value={"Authorization": "Bearer t"})
    return obj


def test_agents_importer_getters(importer):
    assert importer.get_required_fields() == []
    assert importer.get_item_type() == "IdentityGatewayAgent agents"


def test_agents_importer_get_api_endpoint(importer):
    url = importer.get_api_endpoint("id1", "https://x")
    assert url.endswith("/realm-config/agents/IdentityGatewayAgent/id1")


def test_agents_importer_build_payload_removes_rev(importer):
    payload = importer._build_payload({"_id": "a", "_rev": "1", "x": 1})
    data = json.loads(payload)
    assert "_rev" not in data
    assert data["_id"] == "a"
    assert data["x"] == 1


def test_agents_importer_update_item_missing_id(mocker):
    importer = AgentsImporter("WebAgent", realm="alpha")
    mocker.patch("trxo.commands.imports.agents.error")
    ok = importer.update_item({}, "t", "https://x")
    assert ok is False


def test_agents_importer_update_item_success(mocker):
    importer = AgentsImporter("WebAgent", realm="alpha")
    mocker.patch.object(importer, "make_http_request")
    mocker.patch.object(importer, "build_auth_headers", return_value={})
    mocker.patch("trxo.commands.imports.agents.info")
    ok = importer.update_item({"_id": "x", "a": 1}, "t", "https://x")
    assert ok is True


def test_agents_importer_update_item_failure(mocker):
    importer = AgentsImporter("WebAgent", realm="alpha")
    mocker.patch.object(importer, "make_http_request", side_effect=Exception("boom"))
    mocker.patch.object(importer, "build_auth_headers", return_value={})
    mocker.patch("trxo.commands.imports.agents.error")
    ok = importer.update_item({"_id": "x"}, "t", "https://x")
    assert ok is False


def test_import_identity_gateway_agents_calls_importer(mocker):
    importer = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.agents.AgentsImporter",
        return_value=importer,
    )

    gateway, _, _ = create_agents_import_command()
    gateway()

    importer.import_from_file.assert_called_once()


def test_import_java_agents_calls_importer(mocker):
    importer = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.agents.AgentsImporter",
        return_value=importer,
    )

    _, java, _ = create_agents_import_command()
    java()

    importer.import_from_file.assert_called_once()


def test_import_web_agents_calls_importer(mocker):
    importer = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.agents.AgentsImporter",
        return_value=importer,
    )

    _, _, web = create_agents_import_command()
    web()

    importer.import_from_file.assert_called_once()


def test_import_agents_with_args(mocker):
    importer = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.agents.AgentsImporter",
        return_value=importer,
    )

    gateway, _, _ = create_agents_import_command()
    gateway(
        file="f.json",
        realm="bravo",
        cherry_pick="x",
        jwk_path="k",
        client_id="c",
        sa_id="s",
        base_url="b",
        project_name="p",
        auth_mode="onprem",
        onprem_username="u",
        onprem_password="pw",
        onprem_realm="root",
        force_import=True,
        diff=True,
        branch="dev",
    )

    kwargs = importer.import_from_file.call_args.kwargs
    assert kwargs["file_path"] == "f.json"
    assert kwargs["realm"] == "bravo"
    assert kwargs["cherry_pick"] == "x"
    assert kwargs["force_import"] is True
    assert kwargs["diff"] is True
    assert kwargs["branch"] == "dev"


def test_agents_callback_with_subcommand_no_exit():
    callback = create_agents_callback()
    ctx = type("X", (), {"invoked_subcommand": "gateway"})()
    callback(ctx)
