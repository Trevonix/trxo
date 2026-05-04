import json
import pytest
from trxo.commands.imports.agents import (
    create_agents_callback,
    create_agents_import_command,
)
from trxo_lib.imports.domains.agents import AgentsImporter


@pytest.fixture
def importer(mocker):
    obj = AgentsImporter("IdentityGatewayAgent", realm="alpha")
    mocker.patch.object(obj, "make_http_request")
    mocker.patch.object(
        obj, "build_auth_headers", return_value={"Authorization": "Bearer t"}
    )
    return obj


def test_agents_importer_getters(importer):
    assert importer.get_required_fields() == []
    assert importer.get_item_type() == "agents_gateway"


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
    mocker.patch("trxo_lib.imports.domains.agents.error")
    ok = importer.update_item({}, "t", "https://x")
    assert ok is False


def test_agents_importer_update_item_success(mocker):
    importer = AgentsImporter("WebAgent", realm="alpha")
    mocker.patch.object(importer, "make_http_request")
    mocker.patch.object(importer, "build_auth_headers", return_value={})
    mocker.patch("trxo_lib.imports.domains.agents.info")
    ok = importer.update_item({"_id": "x", "a": 1}, "t", "https://x")
    assert ok is True


def test_agents_importer_update_item_failure(mocker):
    importer = AgentsImporter("WebAgent", realm="alpha")
    mocker.patch.object(importer, "make_http_request", side_effect=Exception("boom"))
    mocker.patch.object(importer, "build_auth_headers", return_value={})
    mocker.patch("trxo_lib.imports.domains.agents.error")
    ok = importer.update_item({"_id": "x"}, "t", "https://x")
    assert ok is False


def test_import_identity_gateway_agents_wires_service(mocker):
    mock_service = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.agents.ImportService", return_value=mock_service
    )

    gateway, _, _ = create_agents_import_command()
    gateway()

    mock_service.import_agents.assert_called_once()
    assert (
        mock_service.import_agents.call_args.kwargs["agent_type"]
        == "IdentityGatewayAgent"
    )


def test_import_java_agents_wires_service(mocker):
    mock_service = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.agents.ImportService", return_value=mock_service
    )

    _, java, _ = create_agents_import_command()
    java()

    mock_service.import_agents.assert_called_once()
    assert mock_service.import_agents.call_args.kwargs["agent_type"] == "J2EEAgent"


def test_import_web_agents_wires_service(mocker):
    mock_service = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.agents.ImportService", return_value=mock_service
    )

    _, _, web = create_agents_import_command()
    web()

    mock_service.import_agents.assert_called_once()
    assert mock_service.import_agents.call_args.kwargs["agent_type"] == "WebAgent"


def test_agents_callback_with_subcommand_no_exit():
    callback = create_agents_callback()
    ctx = type("X", (), {"invoked_subcommand": "gateway"})()
    callback(ctx)
