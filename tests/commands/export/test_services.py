import pytest

from trxo.commands.export.services import create_services_export_command


class DummyResponse:
    def __init__(self, json_data=None):
        self._json = json_data

    def json(self):
        return self._json


@pytest.fixture
def mock_exporter(mocker):
    exporter = mocker.Mock()
    exporter.build_auth_headers.return_value = {"Authorization": "Bearer token"}
    exporter._construct_api_url.side_effect = lambda base, ep: f"{base}{ep}"
    exporter.get_current_auth.return_value = ("token", "https://api.example.com")
    mocker.patch("trxo.commands.export.services.ServicesExporter", return_value=exporter)
    return exporter


def test_export_services_scope_global(mock_exporter):
    export_services = create_services_export_command()

    export_services(scope="global")

    kwargs = mock_exporter.export_data.call_args.kwargs

    assert kwargs["command_name"] == "services"
    assert kwargs["api_endpoint"] == "/am/json/global-config/services?_queryFilter=true"
    assert callable(kwargs["response_filter"])


def test_export_services_scope_realm(mock_exporter):
    export_services = create_services_export_command()

    export_services(scope="realm", realm="alpha")

    kwargs = mock_exporter.export_data.call_args.kwargs

    assert "realms/alpha/realm-config/services" in kwargs["api_endpoint"]


def test_export_services_invalid_scope(mocker):
    exporter = mocker.Mock()
    mocker.patch("trxo.commands.export.services.ServicesExporter", return_value=exporter)
    error_spy = mocker.patch("trxo.utils.console.error")

    export_services = create_services_export_command()

    with pytest.raises(Exception):
        export_services(scope="bad")

    error_spy.assert_called_once()



def test_services_response_filter_non_dict(mock_exporter):
    export_services = create_services_export_command()
    export_services(scope="realm")

    response_filter = mock_exporter.export_data.call_args.kwargs["response_filter"]

    raw = ["not", "a", "dict"]
    assert response_filter(raw) == raw


def test_services_response_filter_empty_result(mock_exporter):
    export_services = create_services_export_command()
    export_services(scope="realm")

    response_filter = mock_exporter.export_data.call_args.kwargs["response_filter"]

    raw = {"result": []}
    assert response_filter(raw) == raw


def test_services_response_filter_missing_auth(mock_exporter, mocker):
    mock_exporter.get_current_auth.return_value = (None, None)
    warn_spy = mocker.patch("trxo.commands.export.services.warning")

    export_services = create_services_export_command()
    export_services(scope="realm")

    response_filter = mock_exporter.export_data.call_args.kwargs["response_filter"]

    raw = {"result": [{"_id": "ServiceA"}]}
    out = response_filter(raw)

    assert out == raw
    warn_spy.assert_called_once()


def test_services_response_filter_skips_datastore_service(mock_exporter):
    export_services = create_services_export_command()
    export_services(scope="realm")

    response_filter = mock_exporter.export_data.call_args.kwargs["response_filter"]

    raw = {"result": [{"_id": "DataStoreService"}]}
    out = response_filter(raw)

    assert out["result"] == []


def test_services_response_filter_success_with_descendants(mock_exporter):
    mock_exporter.make_http_request.side_effect = [
        DummyResponse({"_id": "ServiceA"}),
        DummyResponse({"result": [{"_rev": "1", "x": 1}]}),
    ]

    export_services = create_services_export_command()
    export_services(scope="realm", realm="alpha")

    response_filter = mock_exporter.export_data.call_args.kwargs["response_filter"]

    raw = {"result": [{"_id": "ServiceA"}]}
    out = response_filter(raw)

    assert out["result"][0]["_id"] == "ServiceA"
    assert out["result"][0]["nextDescendents"] == [{"x": 1}]


def test_services_response_filter_nextdescendents_failure(mock_exporter):
    mock_exporter.make_http_request.side_effect = [
        DummyResponse({"_id": "ServiceA"}),
        Exception("boom"),
    ]

    export_services = create_services_export_command()
    export_services(scope="realm", realm="alpha")

    response_filter = mock_exporter.export_data.call_args.kwargs["response_filter"]

    raw = {"result": [{"_id": "ServiceA"}]}
    out = response_filter(raw)

    assert out["result"][0]["nextDescendents"] == []


def test_services_response_filter_detail_fetch_failure(mock_exporter, mocker):
    mock_exporter.make_http_request.side_effect = Exception("boom")
    warn_spy = mocker.patch("trxo.commands.export.services.warning")

    export_services = create_services_export_command()
    export_services(scope="realm", realm="alpha")

    response_filter = mock_exporter.export_data.call_args.kwargs["response_filter"]

    raw = {"result": [{"_id": "ServiceA"}]}
    out = response_filter(raw)

    assert out["result"][0] == {"_id": "ServiceA"}
    warn_spy.assert_called_once()
