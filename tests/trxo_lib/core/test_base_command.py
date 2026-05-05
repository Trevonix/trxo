import json
import os
import pytest
import httpx
from unittest.mock import MagicMock, patch
from trxo_lib.core.base_command import BaseCommand
from trxo_lib.exceptions import TrxoAbort, TrxoAuthError, TrxoError, TrxoIOError, TrxoValidationError

# Concrete implementation for testing
class ConcreteCommand(BaseCommand):
    def get_required_fields(self):
        return ["_id"]
    def get_item_type(self):
        return "items"

@pytest.fixture
def base_command():
    with patch("trxo_lib.core.base_command.ConfigStore"):
        with patch("trxo_lib.core.base_command.TokenManager"):
            with patch("trxo_lib.core.base_command.AuthManager"):
                return ConcreteCommand()

def test_construct_api_url(base_command):
    with patch("trxo_lib.core.base_command.construct_api_url") as mock_util:
        mock_util.return_value = "http://api.com/v1"
        assert base_command._construct_api_url("http://api.com", "/v1") == "http://api.com/v1"

def test_initialize_auth_local(base_command):
    base_command.auth_manager.validate_project.return_value = "proj"
    base_command.auth_manager.get_auth_mode.return_value = "service-account"
    base_command.auth_manager.get_base_url.return_value = "http://base.com"
    base_command.auth_manager.get_token.return_value = "token123"
    
    token, url = base_command.initialize_auth()
    assert token == "token123"
    assert url == "http://base.com"
    assert base_command.auth_mode == "service-account"

def test_initialize_auth_onprem_am(base_command):
    base_command.auth_manager.validate_project.return_value = "proj"
    base_command.auth_manager.get_auth_mode.return_value = "onprem"
    base_command.product = "am"
    base_command.auth_manager.get_base_url.return_value = "http://am.com"
    base_command.auth_manager.get_onprem_session.return_value = "session123"
    
    token, url = base_command.initialize_auth()
    assert token == "session123"
    assert url == "http://am.com"
    assert base_command.auth_mode == "onprem"

def test_initialize_auth_onprem_idm(base_command):
    base_command.auth_manager.validate_project.return_value = "proj"
    base_command.auth_manager.get_auth_mode.return_value = "onprem"
    base_command.product = "idm"
    base_command.auth_manager.get_idm_credentials.return_value = ("admin", "pass")
    base_command.auth_manager.get_idm_base_url.return_value = "http://idm.com"
    
    token, url = base_command.initialize_auth()
    assert url == "http://idm.com"
    assert base_command._idm_username == "admin"

def test_initialize_auth_onprem_idm_failure(base_command):
    base_command.auth_manager.validate_project.return_value = "proj"
    base_command.auth_manager.get_auth_mode.return_value = "onprem"
    base_command.product = "idm"
    base_command.auth_manager.get_idm_credentials.side_effect = TrxoAuthError("failed")
    with pytest.raises(TrxoAuthError):
        base_command.initialize_auth()

def test_build_auth_headers_local(base_command):
    base_command.auth_mode = "service-account"
    headers = base_command.build_auth_headers("token123")
    assert headers == {"Authorization": "Bearer token123"}

def test_build_auth_headers_onprem_am(base_command):
    base_command.auth_mode = "onprem"
    base_command.product = "am"
    headers = base_command.build_auth_headers("session123")
    assert headers == {"Cookie": "iPlanetDirectoryPro=session123"}

def test_build_auth_headers_onprem_am_missing_token(base_command):
    base_command.auth_mode = "onprem"
    base_command.product = "am"
    with pytest.raises(TrxoAuthError):
        base_command.build_auth_headers(None)

def test_build_auth_headers_onprem_idm(base_command):
    base_command.auth_mode = "onprem"
    base_command.product = "idm"
    base_command._idm_username = "admin"
    base_command._idm_password = "password"
    headers = base_command.build_auth_headers(None)
    assert headers == {"X-OpenIDM-Username": "admin", "X-OpenIDM-Password": "password"}

def test_cleanup(base_command):
    base_command.cleanup()
    base_command.auth_manager.cleanup_argument_mode.assert_called_once()

def test_load_data_from_file_success(base_command, tmp_path):
    f = tmp_path / "data.json"
    f.write_text(json.dumps({"data": {"result": [{"_id": "1"}]}}))
    items = base_command.load_data_from_file(str(f))
    assert len(items) == 1

def test_load_data_from_file_invalid_structure(base_command, tmp_path):
    f = tmp_path / "data.json"
    f.write_text(json.dumps(["not-a-dict"]))
    with pytest.raises(TrxoValidationError) as exc:
        base_command.load_data_from_file(str(f))
    assert "Invalid JSON structure" in str(exc.value)

def test_load_data_from_file_missing_data(base_command, tmp_path):
    f = tmp_path / "data.json"
    f.write_text(json.dumps({"wrong": "field"}))
    with pytest.raises(TrxoValidationError):
        base_command.load_data_from_file(str(f))

def test_load_data_from_file_invalid_result_list(base_command, tmp_path):
    f = tmp_path / "data.json"
    f.write_text(json.dumps({"data": {"result": "not-a-list"}}))
    with pytest.raises(TrxoValidationError):
        base_command.load_data_from_file(str(f))

def test_load_data_from_file_invalid_item_dict(base_command, tmp_path):
    f = tmp_path / "data.json"
    f.write_text(json.dumps({"data": {"result": ["not-a-dict"]}}))
    with pytest.raises(TrxoValidationError):
        base_command.load_data_from_file(str(f))

def test_load_data_from_file_missing_required(base_command, tmp_path):
    f = tmp_path / "data.json"
    f.write_text(json.dumps({"data": {"result": [{"name": "missing id"}]}}))
    with pytest.raises(TrxoValidationError):
        base_command.load_data_from_file(str(f))

def test_load_data_from_file_generic_exception(base_command, tmp_path):
    f = tmp_path / "data.json"
    f.write_text(json.dumps({"data": {"result": []}}))
    with patch("json.loads", side_effect=Exception("error")):
        with pytest.raises(TrxoIOError):
            base_command.load_data_from_file(str(f))

def test_make_http_request_success(base_command):
    with patch("httpx.Client") as mock_client:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.content = b""
        mock_response.headers = {}
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        resp = base_command.make_http_request("url")
        assert resp.status_code == 200

def test_make_http_request_error_extractions(base_command):
    with patch("httpx.Client") as mock_client:
        client = mock_client.return_value.__enter__.return_value
        
        # Test message
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 400
        resp.json.return_value = {"message": "Msg"}
        resp.headers = {}
        resp.raise_for_status.side_effect = httpx.HTTPStatusError("error", request=MagicMock(), response=resp)
        client.get.return_value = resp
        with pytest.raises(TrxoIOError) as exc:
            base_command.make_http_request("url")
        assert "Msg" in str(exc.value)
        
        # Test reason
        resp.json.return_value = {"reason": "Reason"}
        with pytest.raises(TrxoIOError) as exc:
            base_command.make_http_request("url")
        assert "Reason" in str(exc.value)
        
        # Test error_description
        resp.json.return_value = {"error_description": "Desc"}
        with pytest.raises(TrxoIOError) as exc:
            base_command.make_http_request("url")
        assert "Desc" in str(exc.value)

def test_print_summary(base_command):
    base_command.successful_updates = 1
    base_command.failed_updates = 0
    with patch.object(base_command, "logger"):
        base_command.print_summary()
    
    base_command.failed_updates = 1
    with patch.object(base_command, "logger"):
        with pytest.raises(TrxoAbort):
            base_command.print_summary()
