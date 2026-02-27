import base64
import pytest

from trxo.commands.export.saml import (
    create_saml_export_command,
    process_saml_response,
    extract_script_ids,
    fetch_scripts,
)


class DummyResponse:
    def __init__(self, json_data=None, text="", status_code=200):
        self._json = json_data
        self.text = text
        self.status_code = status_code

    def json(self):
        return self._json


@pytest.fixture
def mock_exporter(mocker):
    exporter = mocker.Mock()
    exporter.build_auth_headers.return_value = {"Authorization": "Bearer token"}
    exporter._construct_api_url.side_effect = lambda base, ep: f"{base}{ep}"
    exporter.get_current_auth.return_value = ("token", "https://api.example.com")
    return exporter


def test_extract_script_ids_nested_and_unique():
    data = {
        "preScript": "123e4567-e89b-12d3-a456-426614174000",
        "nested": {
            "postScript": "abcd-efgh-ijkl-1234567890",
        },
        "list": [
            {"anotherScript": "abcd-efgh-ijkl-1234567890"},
            {"x": 1},
        ],
    }

    ids = extract_script_ids(data)

    assert len(ids) == 2
    assert "123e4567-e89b-12d3-a456-426614174000" in ids
    assert "abcd-efgh-ijkl-1234567890" in ids


def test_fetch_scripts_success_and_decode(mock_exporter):
    script_id = "script1"
    script_body = base64.b64encode(b"print('hi')\nline2").decode("utf-8")

    mock_exporter.make_http_request.return_value = DummyResponse(
        {"_id": script_id, "script": script_body}
    )

    scripts = []

    fetch_scripts(
        exporter_instance=mock_exporter,
        realm="alpha",
        script_ids=[script_id],
        scripts_list=scripts,
        token="token",
        api_base_url="https://api.example.com",
    )

    assert len(scripts) == 1
    assert scripts[0]["_id"] == script_id
    assert scripts[0]["script"] == ["print('hi')", "line2"]


def test_fetch_scripts_decode_failure_keeps_original(mock_exporter, mocker):
    bad_script = "!!!notbase64!!!"

    mock_exporter.make_http_request.return_value = DummyResponse(
        {"_id": "script1", "script": bad_script, "name": "bad"}
    )

    warn_spy = mocker.patch("trxo.commands.export.saml.warning")

    scripts = []

    fetch_scripts(
        exporter_instance=mock_exporter,
        realm="alpha",
        script_ids=["script1"],
        scripts_list=scripts,
        token="token",
        api_base_url="https://api.example.com",
    )

    assert len(scripts) == 1
    assert scripts[0]["script"] == bad_script
    warn_spy.assert_called_once()


def test_fetch_scripts_skips_duplicates(mock_exporter):
    mock_exporter.make_http_request.return_value = DummyResponse({"_id": "script1"})

    scripts = [{"_id": "script1"}]

    fetch_scripts(
        exporter_instance=mock_exporter,
        realm="alpha",
        script_ids=["script1"],
        scripts_list=scripts,
        token="token",
        api_base_url="https://api.example.com",
    )

    assert len(scripts) == 1


def test_process_saml_response_happy_path(mock_exporter, mocker):
    providers = {
        "result": [
            {"_id": "h1", "location": "hosted", "entityId": "eid1"},
            {"_id": "r1", "location": "remote", "entityId": "eid2"},
        ]
    }

    provider_detail = {"_id": "h1", "preScript": "uuid-script-1234567890"}

    mock_exporter.make_http_request.side_effect = [
        DummyResponse(providers),
        DummyResponse(provider_detail),
        DummyResponse(provider_detail),
        DummyResponse(text="<xml/>"),
        DummyResponse(text="<xml/>"),
    ]

    mocker.patch(
        "trxo.commands.export.saml.extract_script_ids",
        return_value=["script1"],
    )
    mocker.patch("trxo.commands.export.saml.fetch_scripts")

    filter_fn = process_saml_response(mock_exporter, "alpha")

    result = filter_fn({})

    assert "hosted" in result
    assert "remote" in result
    assert "metadata" in result
    assert "scripts" in result
    assert len(result["hosted"]) == 1
    assert len(result["remote"]) == 1
    assert len(result["metadata"]) == 2


def test_process_saml_response_no_providers(mock_exporter, mocker):
    mock_exporter.make_http_request.return_value = DummyResponse({"result": []})

    info_spy = mocker.patch("trxo.commands.export.saml.info")

    filter_fn = process_saml_response(mock_exporter, "alpha")
    result = filter_fn({})

    assert result == {"hosted": [], "remote": [], "metadata": [], "scripts": []}
    info_spy.assert_called_once()


def test_process_saml_response_provider_fetch_error(mock_exporter, mocker):
    mock_exporter.make_http_request.side_effect = Exception("boom")

    err_spy = mocker.patch("trxo.commands.export.saml.error")

    filter_fn = process_saml_response(mock_exporter, "alpha")
    result = filter_fn({})

    assert result == {"hosted": [], "remote": [], "metadata": [], "scripts": []}
    err_spy.assert_called_once()


def test_create_saml_export_command_wires_response_filter(mocker):
    exporter = mocker.Mock()
    mocker.patch("trxo.commands.export.saml.BaseExporter", return_value=exporter)

    export_saml = create_saml_export_command()
    export_saml(realm="alpha")

    kwargs = exporter.export_data.call_args.kwargs

    assert kwargs["command_name"] == "saml"
    assert callable(kwargs["response_filter"])
