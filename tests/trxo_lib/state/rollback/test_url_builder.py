import pytest
from unittest.mock import MagicMock, patch
from trxo_lib.state.rollback.url_builder import RollbackUrlBuilder
from trxo_lib.exceptions import TrxoError

@pytest.fixture
def baseline():
    return {
        "n1": {"_type": {"_id": "PageNode"}},
        "e1": {"_id": "e1", "name": "Template"},
        "s1": {"_id": "s1", "_saml_location": "remote"},
        "p1": {"_id": "p1", "applicationName": "app1"}, # Policy
        "ps1": {"_id": "ps1"}, # Policy Set
    }

def test_build_api_url_script(baseline):
    builder = RollbackUrlBuilder("oauth", "alpha", baseline)
    url = builder.build_api_url("script::abc", "http://base")
    assert "/scripts/abc" in url
    assert "alpha" in url

def test_build_api_url_managed(baseline):
    builder = RollbackUrlBuilder("managed", "alpha", baseline)
    with patch("trxo_lib.state.rollback.url_builder.get_command_api_endpoint", return_value=("/openidm/managed/alpha_user", None)):
        url = builder.build_api_url("any", "http://base")
        assert "/openidm/managed/alpha_user" in url

def test_build_api_url_nodes(baseline):
    builder = RollbackUrlBuilder("nodes", "alpha", baseline)
    # Success case
    url = builder.build_api_url("n1", "http://base")
    assert "/nodes/PageNode/n1" in url
    
    # Missing from baseline
    url = builder.build_api_url("unknown", "http://base")
    assert "/nodes/unknown/unknown" in url

def test_build_api_url_email_templates(baseline):
    builder = RollbackUrlBuilder("email_templates", "alpha", baseline)
    url = builder.build_api_url("e1", "http://base/am")
    assert "http://base/openidm/config/emailTemplate/e1" == url

def test_build_api_url_saml(baseline):
    builder = RollbackUrlBuilder("saml", "alpha", baseline)
    # Hosted entity (default)
    url = builder.build_api_url("h1", "http://base")
    assert "/saml2/hosted/h1" in url
    
    # Remote entity (from baseline)
    url = builder.build_api_url("s1", "http://base")
    assert "/saml2/remote/s1" in url

def test_build_api_url_policies(baseline):
    builder = RollbackUrlBuilder("policies", "alpha", baseline)
    # Policy
    url = builder.build_api_url("p1", "http://base")
    assert "/policies/p1" in url
    
    # Policy Set
    url = builder.build_api_url("ps1", "http://base")
    assert "/applications/ps1" in url

def test_build_api_url_standard(baseline):
    builder = RollbackUrlBuilder("oauth", "alpha", baseline)
    with patch("trxo_lib.state.rollback.url_builder.get_command_api_endpoint", return_value=("/am/json/agents/OAuth2Client", None)):
        url = builder.build_api_url("c1", "http://base")
        assert "/am/json/agents/OAuth2Client/c1" in url

def test_build_api_url_exception(baseline):
    builder = RollbackUrlBuilder("fail", "alpha", baseline)
    # Simulate get_command_api_endpoint returning None or raising
    with patch("trxo_lib.state.rollback.url_builder.get_command_api_endpoint", return_value=(None, None)):
        url = builder.build_api_url("item", "http://base")
        assert "http://base/item" == url

def test_build_standard_url_no_endpoint(baseline):
    builder = RollbackUrlBuilder("unknown", "alpha", baseline)
    with patch("trxo_lib.state.rollback.url_builder.get_command_api_endpoint", return_value=(None, None)):
        with pytest.raises(TrxoError, match="Unknown API endpoint"):
            builder._build_standard_url("item", "http://base")
