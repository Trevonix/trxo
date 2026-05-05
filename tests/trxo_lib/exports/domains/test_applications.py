import pytest
from unittest.mock import MagicMock, patch
from trxo_lib.exports.domains.applications import (
    _collect_oidc_client_ids,
    _normalize_provider_export,
    ApplicationsExportService,
    _export_applications_with_deps
)

def test_collect_oidc_client_ids():
    apps = [
        {"ssoEntities": {"oidcId": "client1"}},
        {"ssoEntities": {"oidcId": "client2 "}}, 
        {"ssoEntities": {"oidcId": "client1"}}, 
        {"no_sso": {}},
        "not-a-dict"
    ]
    ids = _collect_oidc_client_ids(apps)
    assert ids == ["client1", "client2"]

def test_normalize_provider_export():
    p = {"name": "Test"}
    norm = _normalize_provider_export(p)
    assert norm["_type"]["_id"] == "oauth-oidc"
    assert _normalize_provider_export(None) == {}

def test_applications_export_service_simple():
    with patch("trxo_lib.exports.domains.applications.BaseExporter") as mock_exporter_class:
        mock_exporter = mock_exporter_class.return_value
        service = ApplicationsExportService(realm="root", with_deps=False)
        service.execute()
        mock_exporter.export_data.assert_called_once()

def test_applications_export_service_with_deps_ignored_in_view():
    with patch("trxo_lib.exports.domains.applications.warning") as mock_warning:
        with patch("trxo_lib.exports.domains.applications.BaseExporter") as mock_exporter_class:
            service = ApplicationsExportService(realm="root", with_deps=True, view=True)
            service.execute()
            mock_warning.assert_called_once_with("--with-deps is ignored when using --view")

def test_applications_export_service_execute_with_deps():
    with patch("trxo_lib.exports.domains.applications._export_applications_with_deps") as mock_export:
        service = ApplicationsExportService(realm="root", with_deps=True)
        service.execute()
        mock_export.assert_called_once()

def test_applications_export_service_commit_mapping():
    with patch("trxo_lib.exports.domains.applications.BaseExporter") as mock_exporter_class:
        mock_exporter = mock_exporter_class.return_value
        service = ApplicationsExportService(realm="root", commit="feat: add app")
        service.execute()
        args = mock_exporter.export_data.call_args[1]
        assert args["commit_message"] == "feat: add app"

@patch("trxo_lib.exports.domains.applications.BaseExporter")
@patch("trxo_lib.exports.domains.applications.OAuthExporter")
def test_export_applications_with_deps_success(mock_oauth_class, mock_base_class):
    mock_base = mock_base_class.return_value
    mock_base.initialize_auth.return_value = ("token", "http://api.com")
    mock_base.auth_mode = "local"
    mock_base.build_auth_headers.return_value = {}
    mock_base._construct_api_url.return_value = "http://api.com/apps"
    
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [{"ssoEntities": {"oidcId": "c1"}}]}
    mock_resp.status_code = 200
    mock_base.make_http_request.return_value = mock_resp
    mock_base._handle_pagination.return_value = {"result": [{"ssoEntities": {"oidcId": "c1"}}]}
    mock_base.remove_rev_fields.return_value = {"result": [{"ssoEntities": {"oidcId": "c1"}}]}
    
    mock_oauth = mock_oauth_class.return_value
    mock_oauth.fetch_oauth_client_data.return_value = {"_id": "c1"}
    mock_oauth.extract_script_ids.return_value = []
    mock_oauth.fetch_oauth_provider_data.return_value = {"_id": "p1"}
    
    _export_applications_with_deps(
        realm="alpha", version=None, no_version=False, branch=None, commit=None,
        jwk_path=None, sa_id=None, base_url=None, project_name=None,
        output_dir=None, output_file=None, auth_mode=None,
        onprem_username=None, onprem_password=None, onprem_realm=None, am_base_url=None,
        idm_base_url=None, idm_username=None, idm_password=None
    )
    
    mock_base.save_response.assert_called_once()

@patch("trxo_lib.exports.domains.applications.BaseExporter")
@patch("trxo_lib.exports.domains.applications.OAuthExporter")
def test_export_applications_with_deps_onprem(mock_oauth_class, mock_base_class):
    mock_base = mock_base_class.return_value
    mock_base.initialize_auth.return_value = ("idm-token", "http://idm.com")
    mock_base.auth_mode = "onprem"
    mock_base.product = "idm"
    mock_base._idm_base_url = "http://idm.com"
    mock_base.build_auth_headers.return_value = {}
    mock_base.make_http_request.return_value.json.return_value = {"result": []}
    mock_base.make_http_request.return_value.status_code = 400
    mock_base._handle_pagination.return_value = {"result": []}
    mock_base.remove_rev_fields.return_value = {"result": []}
    mock_base._get_storage_mode.return_value = "local"
    mock_base.save_response.return_value = "/path/to/file"
    
    mock_oauth = mock_oauth_class.return_value
    mock_oauth.initialize_auth.return_value = ("am-token", "http://am.com")
    mock_oauth.fetch_oauth_provider_data.return_value = {"_id": "p1"}
    mock_oauth.extract_script_ids.return_value = ["s1"]
    mock_oauth.fetch_script_data.return_value = {"_id": "s1"}
    
    _export_applications_with_deps(
        realm="root", version=None, no_version=False, branch=None, commit=None,
        jwk_path=None, sa_id=None, base_url=None, project_name=None,
        output_dir=None, output_file=None, auth_mode="onprem",
        onprem_username="u", onprem_password="p", onprem_realm="r", am_base_url="http://am",
        idm_base_url="http://idm", idm_username="iu", idm_password="ip"
    )
    
    mock_oauth.fetch_script_data.assert_called()
    mock_base.cleanup.assert_called()
    mock_oauth.cleanup.assert_called()

def test_export_applications_with_deps_failure():
    with patch("trxo_lib.exports.domains.applications.BaseExporter") as mock_base_class:
        mock_base = mock_base_class.return_value
        mock_base.initialize_auth.side_effect = Exception("auth failed")
        from trxo_lib.exceptions import TrxoAbort
        with pytest.raises(TrxoAbort):
            _export_applications_with_deps(
                realm="alpha", version=None, no_version=False, branch=None, commit=None,
                jwk_path=None, sa_id=None, base_url=None, project_name=None,
                output_dir=None, output_file=None, auth_mode=None,
                onprem_username=None, onprem_password=None, onprem_realm=None, am_base_url=None,
                idm_base_url=None, idm_username=None, idm_password=None
            )
