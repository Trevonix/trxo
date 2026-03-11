import json

import pytest  # noqa: F401 – kept for pytest.raises if needed in future

from trxo.commands.imports.journeys import (
    JourneyImporter,
    _scripts_needed_by_trees,
    create_journey_import_command,
)

# ---------------------------------------------------------------------------
# Basic contract tests
# ---------------------------------------------------------------------------


def test_journey_required_fields():
    importer = JourneyImporter()
    assert importer.get_required_fields() == ["_id"]


def test_journey_item_type():
    importer = JourneyImporter()
    assert importer.get_item_type() == "journeys"


def test_journey_api_endpoint():
    importer = JourneyImporter(realm="alpha")
    url = importer.get_api_endpoint("j1", "http://x")
    assert url.endswith(
        "/am/json/realms/root/realms/alpha/realm-config/authentication/authenticationtrees/trees/j1"
    )


# ---------------------------------------------------------------------------
# update_item (single journey PUT)
# ---------------------------------------------------------------------------


def test_journey_update_success(mocker):
    importer = JourneyImporter()
    importer.make_http_request = mocker.Mock()

    data = {"_id": "j1", "_rev": "1", "name": "test"}
    assert importer.update_item(data, "tok", "http://x") is True
    importer.make_http_request.assert_called_once()


def test_journey_update_missing_id(mocker):
    importer = JourneyImporter()
    mocker.patch("trxo.commands.imports.journeys.error")
    assert importer.update_item({}, "tok", "http://x") is False


def test_journey_update_failure(mocker):
    importer = JourneyImporter()
    importer.make_http_request = mocker.Mock(side_effect=Exception("boom"))
    mocker.patch("trxo.commands.imports.journeys.error")

    data = {"_id": "j1"}
    assert importer.update_item(data, "tok", "http://x") is False


# ---------------------------------------------------------------------------
# _import_single_script
# ---------------------------------------------------------------------------


def test_import_script_missing_id(mocker):
    importer = JourneyImporter()
    mocker.patch("trxo.commands.imports.journeys.error")
    assert importer._import_single_script({"name": "s"}, "tok", "http://x") is False


def test_import_script_list_encoded(mocker):
    importer = JourneyImporter()

    mock_client = mocker.MagicMock()
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_client.__enter__.return_value.put.return_value = mock_response
    mocker.patch("httpx.Client", return_value=mock_client)

    data = {"_id": "s1", "name": "myscript", "script": ["var x = 1;", "var y = 2;"]}
    assert importer._import_single_script(data, "tok", "http://x") is True

    # Verify payload had base64-encoded script
    call_args = mock_client.__enter__.return_value.put.call_args
    sent_payload = call_args[1]["json"]
    import base64

    decoded = base64.b64decode(sent_payload["script"]).decode("utf-8")
    assert "var x = 1;" in decoded


def test_import_script_string_field(mocker):
    importer = JourneyImporter()

    mock_client = mocker.MagicMock()
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_client.__enter__.return_value.put.return_value = mock_response
    mocker.patch("httpx.Client", return_value=mock_client)

    data = {"_id": "s1", "script": "console.log('hi')"}
    assert importer._import_single_script(data, "tok", "http://x") is True


def test_import_script_request_failure(mocker):
    importer = JourneyImporter()
    mocker.patch("httpx.Client", side_effect=Exception("500 err"))
    mocker.patch("trxo.commands.imports.journeys.error")

    data = {"_id": "s1", "script": "x"}
    assert importer._import_single_script(data, "tok", "http://x") is False


# ---------------------------------------------------------------------------
# _import_email_template
# ---------------------------------------------------------------------------


def test_import_email_template_success(mocker):
    importer = JourneyImporter()
    importer.make_http_request = mocker.Mock()

    assert (
        importer._import_email_template(
            "welcome", {"_id": "welcome", "subject": "Hi"}, "tok", "http://x"
        )
        is True
    )


def test_import_email_template_failure(mocker):
    importer = JourneyImporter()
    importer.make_http_request = mocker.Mock(side_effect=Exception("fail"))
    mocker.patch("trxo.commands.imports.journeys.error")

    assert importer._import_email_template("welcome", {}, "tok", "http://x") is False


# ---------------------------------------------------------------------------
# _import_node
# ---------------------------------------------------------------------------


def test_import_node_missing_type(mocker):
    importer = JourneyImporter()
    mocker.patch("trxo.commands.imports.journeys.error")
    assert importer._import_node("n1", {}, "tok", "http://x") is False


def test_import_node_success(mocker):
    importer = JourneyImporter()
    importer.make_http_request = mocker.Mock()

    node = {"_id": "n1", "_type": {"_id": "PageNode"}, "pageName": "Page 1"}
    assert importer._import_node("n1", node, "tok", "http://x") is True


def test_import_node_failure(mocker):
    importer = JourneyImporter()
    importer.make_http_request = mocker.Mock(side_effect=Exception("500"))
    mocker.patch("trxo.commands.imports.journeys.error")

    node = {"_type": {"_id": "PageNode"}}
    assert importer._import_node("n1", node, "tok", "http://x") is False


# ---------------------------------------------------------------------------
# import_journey_data — enriched format
# ---------------------------------------------------------------------------


def _make_enriched(
    trees=None, nodes=None, inner_nodes=None, scripts=None, email_templates=None
):
    return {
        "trees": trees or {},
        "nodes": nodes or {},
        "innerNodes": inner_nodes or {},
        "scripts": scripts or {},
        "emailTemplates": email_templates or {},
        "saml2Entities": {},
        "saml2CirclesOfTrust": {},
        "socialIdentityProviders": {},
        "themes": {},
    }


def test_import_journey_data_empty(mocker):
    importer = JourneyImporter()
    mocker.patch("trxo.commands.imports.journeys.warning")
    assert importer.import_journey_data({}, "tok", "http://x") is True


def test_import_journey_data_scripts_imported_first(mocker):
    """Scripts must be imported before trees."""
    call_order = []

    importer = JourneyImporter()
    importer._import_single_script = mocker.Mock(
        side_effect=lambda *a, **kw: call_order.append("script") or True
    )
    importer.update_item = mocker.Mock(
        side_effect=lambda *a, **kw: call_order.append("tree") or True
    )
    importer._import_email_template = mocker.Mock(return_value=True)
    importer._import_node = mocker.Mock(return_value=True)
    mocker.patch("trxo.commands.imports.journeys.info")
    mocker.patch("trxo.commands.imports.journeys.success")

    data = _make_enriched(
        trees={"j1": {"_id": "j1"}},
        scripts={"s1": {"_id": "s1", "script": []}},
    )
    result = importer.import_journey_data(data, "tok", "http://x")

    assert result is True
    assert call_order.index("script") < call_order.index("tree")


def test_import_journey_data_inner_nodes_before_root(mocker):
    """Inner nodes must be imported before root nodes."""
    call_order = []

    importer = JourneyImporter()
    importer._import_single_script = mocker.Mock(return_value=True)
    importer._import_email_template = mocker.Mock(return_value=True)
    importer.update_item = mocker.Mock(return_value=True)
    importer._import_node = mocker.Mock(
        side_effect=lambda nid, *a, **kw: call_order.append(nid) or True
    )
    mocker.patch("trxo.commands.imports.journeys.info")
    mocker.patch("trxo.commands.imports.journeys.success")

    data = _make_enriched(
        trees={"j1": {"_id": "j1"}},
        nodes={"root1": {"_id": "root1", "_type": {"_id": "PageNode"}}},
        inner_nodes={"inner1": {"_id": "inner1", "_type": {"_id": "PageNode"}}},
    )
    importer.import_journey_data(data, "tok", "http://x")

    assert call_order.index("inner1") < call_order.index("root1")


def test_import_journey_data_all_sections(mocker):
    importer = JourneyImporter()
    importer._import_single_script = mocker.Mock(return_value=True)
    importer._import_email_template = mocker.Mock(return_value=True)
    importer._import_node = mocker.Mock(return_value=True)
    importer.update_item = mocker.Mock(return_value=True)
    mocker.patch("trxo.commands.imports.journeys.info")
    mocker.patch("trxo.commands.imports.journeys.success")

    data = _make_enriched(
        trees={"j1": {"_id": "j1"}, "j2": {"_id": "j2"}},
        nodes={"n1": {"_type": {"_id": "T"}}, "n2": {"_type": {"_id": "T"}}},
        inner_nodes={"i1": {"_type": {"_id": "T"}}},
        scripts={"s1": {"_id": "s1"}, "s2": {"_id": "s2"}},
        email_templates={"tmpl": {"_id": "tmpl"}},
    )
    result = importer.import_journey_data(data, "tok", "http://x")

    assert result is True
    assert importer._import_single_script.call_count == 2
    assert importer._import_email_template.call_count == 1
    assert importer._import_node.call_count == 3  # 1 inner + 2 root
    assert importer.update_item.call_count == 2


def test_import_journey_data_error_propagated(mocker):
    importer = JourneyImporter()
    importer._import_single_script = mocker.Mock(return_value=False)
    importer._import_email_template = mocker.Mock(return_value=True)
    importer._import_node = mocker.Mock(return_value=True)
    importer.update_item = mocker.Mock(return_value=True)
    mocker.patch("trxo.commands.imports.journeys.info")
    mocker.patch("trxo.commands.imports.journeys.warning")

    data = _make_enriched(
        trees={"j1": {"_id": "j1"}},
        scripts={"s1": {"_id": "s1"}},
    )
    result = importer.import_journey_data(data, "tok", "http://x")
    assert result is False


# ---------------------------------------------------------------------------
# Cherry-pick filtering
# ---------------------------------------------------------------------------


def test_import_journey_data_cherry_pick(mocker):
    """Only the selected journey and its trees are imported."""
    importer = JourneyImporter()
    importer._import_single_script = mocker.Mock(return_value=True)
    importer._import_email_template = mocker.Mock(return_value=True)
    importer._import_node = mocker.Mock(return_value=True)
    called_trees = []
    importer.update_item = mocker.Mock(
        side_effect=lambda item, *a: called_trees.append(item["_id"]) or True
    )
    mocker.patch("trxo.commands.imports.journeys.info")
    mocker.patch("trxo.commands.imports.journeys.success")

    data = _make_enriched(
        trees={"j1": {"_id": "j1", "nodes": {}}, "j2": {"_id": "j2", "nodes": {}}},
        scripts={"s1": {"_id": "s1"}},
    )
    importer.import_journey_data(data, "tok", "http://x", cherry_pick_ids="j1")

    assert called_trees == ["j1"]


# ---------------------------------------------------------------------------
# _scripts_needed_by_trees helper
# ---------------------------------------------------------------------------


def test_scripts_needed_by_trees():
    data = {
        "trees": {
            "j1": {"nodes": {"n1": {}, "n2": {}}},
            "j2": {"nodes": {"n3": {}}},
        },
        "nodes": {
            "n1": {"script": "sid-a"},
            "n2": {"transformationScript": "sid-b"},
            "n3": {"script": "sid-c"},
        },
        "innerNodes": {},
    }
    needed = _scripts_needed_by_trees(data, ["j1"])
    assert "sid-a" in needed
    assert "sid-b" in needed
    assert "sid-c" not in needed


# ---------------------------------------------------------------------------
# CLI command factory
# ---------------------------------------------------------------------------


def test_create_journey_import_command_calls_import(mocker):
    importer = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.journeys.JourneyImporter",
        return_value=importer,
    )
    cmd = create_journey_import_command()
    cmd(file="f.json", realm="alpha", cherry_pick="a,b")
    importer.import_from_file.assert_called_once()


def test_create_journey_import_command_defaults(mocker):
    importer = mocker.Mock()
    mocker.patch(
        "trxo.commands.imports.journeys.JourneyImporter",
        return_value=importer,
    )
    cmd = create_journey_import_command()
    cmd()
    importer.import_from_file.assert_called_once()


# ---------------------------------------------------------------------------
# Backward compatibility — legacy flat list
# ---------------------------------------------------------------------------


def test_legacy_flat_format_via_import_from_file(mocker, tmp_path):
    """load_data_from_file handles the plain list format (data is a list)."""
    # Write a file with data as a direct list (no result wrapper)
    flat_data = [{"_id": "j1", "name": "Journey One"}]
    export_file = tmp_path / "journeys.json"
    export_file.write_text(json.dumps({"metadata": {}, "data": flat_data}))

    importer = JourneyImporter()
    items = importer.load_data_from_file(str(export_file))
    assert isinstance(items, list)
    assert items[0]["_id"] == "j1"


def test_enriched_format_load_data_from_file(mocker, tmp_path):
    """load_data_from_file on an enriched export returns only the tree values."""
    enriched = {
        "trees": {"j1": {"_id": "j1"}, "j2": {"_id": "j2"}},
        "nodes": {},
        "innerNodes": {},
        "scripts": {},
        "emailTemplates": {},
    }
    export_file = tmp_path / "journeys.json"
    export_file.write_text(json.dumps({"metadata": {}, "data": enriched}))

    importer = JourneyImporter()
    items = importer.load_data_from_file(str(export_file))
    assert isinstance(items, list)
    assert len(items) == 2
    ids = {i["_id"] for i in items}
    assert ids == {"j1", "j2"}
