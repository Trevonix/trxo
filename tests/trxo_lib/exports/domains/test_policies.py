import pytest
from unittest.mock import MagicMock, patch
from trxo_lib.exports.domains.policies import (
    fetch_global_policies,
    process_policies_response,
    PoliciesExporter,
    PoliciesExportService
)

class MockExporter:
    def __init__(self):
        self.get_current_auth = MagicMock()
        self.build_auth_headers = MagicMock()
        self._construct_api_url = MagicMock()
        self.make_http_request = MagicMock()
        self.auth_mode = "local"
        self.logger = MagicMock()

def test_fetch_global_policies_success():
    exporter = MockExporter()
    exporter.get_current_auth.return_value = ("token", "http://base")
    exporter.build_auth_headers.return_value = {}
    exporter._construct_api_url.side_effect = lambda b, e: f"{b}{e}"
    
    # Mock /config response as a LIST
    mock_resp_list = MagicMock()
    mock_resp_list.json.return_value = [{"_id": "fieldPolicy/u1"}, "policy"]
    
    # Mock individual config response
    mock_resp_config = MagicMock()
    mock_resp_config.status_code = 200
    mock_resp_config.json.return_value = {"val": "x"}
    
    # Mock managed discovery
    mock_resp_managed = MagicMock()
    mock_resp_managed.status_code = 200
    mock_resp_managed.json.return_value = {"objects": [{"name": "user"}]}
    
    exporter.make_http_request.side_effect = [
        mock_resp_list, mock_resp_managed, mock_resp_config, mock_resp_config, mock_resp_config
    ]
    
    res = fetch_global_policies(exporter)
    assert len(res) == 3

def test_process_policies_response():
    exporter = MockExporter()
    exporter.get_current_auth.return_value = ("token", "http://base")
    exporter.build_auth_headers.return_value = {}
    exporter._construct_api_url.return_value = "http://url"
    
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [{"_id": "set1"}]}
    exporter.make_http_request.return_value = mock_resp
    
    filter_func = process_policies_response(exporter, "alpha", global_policies=True)
    with patch("trxo_lib.exports.domains.policies.fetch_global_policies", return_value=[{"_id": "g1"}]):
        res = filter_func({"result": [{"_id": "p1"}]})
        assert "am" in res
        assert "global" in res

def test_policies_export_service():
    with patch("trxo_lib.exports.domains.policies.PoliciesExporter") as mock_exporter_class:
        mock_exporter = mock_exporter_class.return_value
        service = PoliciesExportService(realm="alpha", global_policies=True)
        service.execute()
        mock_exporter.export_data.assert_called_once()
