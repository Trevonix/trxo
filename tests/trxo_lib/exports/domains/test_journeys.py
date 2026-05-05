import json
import base64
import pytest
from unittest.mock import MagicMock, patch
from trxo_lib.exports.domains.journeys import (
    _is_uuid,
    _node_type_id,
    JourneyExporter,
    process_journey_response,
    _extract_saml_script_ids,
    _resolve_themes,
    _fetch_all_nodes
)

def test_is_uuid():
    assert _is_uuid("12345678-1234-1234-1234-123456789012") is True
    assert _is_uuid("not-a-uuid") is False
    assert _is_uuid(None) is False

def test_node_type_id():
    assert _node_type_id({"_type": {"_id": "Node1"}}) == "Node1"
    assert _node_type_id({}) == ""

def test_extract_saml_script_ids():
    data = {
        "script": "12345678-1234-1234-1234-123456789012",
        "other": "val",
        "nested": {"attributeMapperScript": "87654321-4321-4321-4321-210987654321"}
    }
    ids = _extract_saml_script_ids(data)
    assert len(ids) == 2
    assert "12345678-1234-1234-1234-123456789012" in ids

def test_resolve_themes():
    export = {"trees": {"tree1": {}}, "nodes": {}, "innerNodes": {}, "themes": {}}
    themes = [
        {"_id": "theme1", "linkedTrees": ["tree1"]},
        {"_id": "theme2", "linkedTrees": ["tree2"]}
    ]
    _resolve_themes(export, themes)
    assert "theme1" in export["themes"]
    assert "theme2" not in export["themes"]

def test_fetch_all_nodes_success():
    exporter = MagicMock()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": [{"_id": "n1", "val": "x"}]}
    exporter.make_http_request.return_value = mock_resp
    exporter._construct_api_url.return_value = "http://api.com"
    
    nodes = _fetch_all_nodes(exporter, "root", "http://base", {})
    assert "n1" in nodes
    assert nodes["n1"]["val"] == "x"

def test_fetch_all_nodes_failure():
    exporter = MagicMock()
    exporter.make_http_request.side_effect = Exception("boom")
    nodes = _fetch_all_nodes(exporter, "root", "http://base", {})
    assert nodes == {}

@patch("trxo_lib.exports.domains.journeys.info")
def test_process_journey_response_empty(mock_info):
    exporter = MagicMock()
    exporter.get_current_auth.return_value = ("token", "http://api.com")
    exporter.build_auth_headers.return_value = {}
    exporter._construct_api_url.return_value = "http://api.com"
    
    # Mock bulk fetches to return empty
    with patch("trxo_lib.exports.domains.journeys._fetch_all_nodes", return_value={}):
        with patch("trxo_lib.exports.domains.journeys._fetch_saml_provider_list", return_value={}):
            with patch("trxo_lib.exports.domains.journeys._fetch_circles_of_trust", return_value={}):
                with patch("trxo_lib.exports.domains.journeys._fetch_social_providers", return_value={}):
                    with patch("trxo_lib.exports.domains.journeys._fetch_themes", return_value=[]):
                        filter_func = process_journey_response(exporter, "alpha")
                        res = filter_func({"result": []})
                        assert res["trees"] == {}
                        mock_info.assert_called()

def test_journey_exporter_export_as_dict():
    exporter = JourneyExporter()
    exporter.save_response = MagicMock()
    exporter.get_current_auth = MagicMock(return_value=("token", "http://api.com"))
    exporter.build_auth_headers = MagicMock(return_value={})
    exporter._construct_api_url = MagicMock(return_value="http://api.com")
    exporter.logger = MagicMock()
    
    with patch.object(exporter, "export_data") as mock_export_data:
        def side_effect(*args, **kwargs):
            # The real export_data sets these, so we mock them
            exporter._current_token = "token"
            exporter._current_api_base_url = "http://api.com"
            
            with patch("trxo_lib.exports.domains.journeys._fetch_all_nodes", return_value={}):
                with patch("trxo_lib.exports.domains.journeys._fetch_saml_provider_list", return_value={}):
                    with patch("trxo_lib.exports.domains.journeys._fetch_circles_of_trust", return_value={}):
                        with patch("trxo_lib.exports.domains.journeys._fetch_social_providers", return_value={}):
                            with patch("trxo_lib.exports.domains.journeys._fetch_themes", return_value=[]):
                                res = kwargs["response_filter"]({"result": [{"_id": "t1"}]})
                                exporter.save_response(res)
        
        mock_export_data.side_effect = side_effect
        res = exporter.export_as_dict(realm="alpha")
        assert "trees" in res
        assert "t1" in res["trees"]

def test_walk_nodes():
    exporter = MagicMock()
    tree = {"nodes": {"n1": {}}}
    node_map = {"n1": {"_type": {"_id": "PageNode"}, "nodes": [{"_id": "n2"}]}, "n2": {"_id": "n2"}}
    export = {"nodes": {}, "innerNodes": {}, "scripts": {}, "emailTemplates": {}, "saml2Entities": {}}
    inner_refs = set()
    
    with patch("trxo_lib.exports.domains.journeys._collect_scripts"):
        with patch("trxo_lib.exports.domains.journeys._collect_email_template"):
            with patch("trxo_lib.exports.domains.journeys._collect_saml"):
                with patch("trxo_lib.exports.domains.journeys._collect_social_providers"):
                    from trxo_lib.exports.domains.journeys import _walk_nodes
                    _walk_nodes(
                        tree=tree, node_map=node_map, export=export, realm="r",
                        exporter=exporter, api_base_url="u", am_hdrs={}, idm_base="i",
                        idm_hdrs={}, saml_provider_list={}, cot_map={}, social_map={},
                        inner_refs=inner_refs
                    )
    
    assert "n1" in export["nodes"]
    assert "n2" in export["innerNodes"]
