import pytest
from unittest.mock import MagicMock

from trxo.utils.diff.insights_generator import InsightsGenerator


def make_item(item_id="id1", name="Item 1", diff=None):
    item = MagicMock()
    item.item_id = item_id
    item.item_name = name
    item.detailed_changes = {"diff": diff or {}}
    return item


def test_generate_key_insights_no_modified_items():
    gen = InsightsGenerator()

    insights = gen.generate_key_insights(
        command_name="oauth",
        added_items=[],
        modified_items=[],
        removed_items=[],
    )

    assert insights == []


def test_oauth_grant_types_insight():
    gen = InsightsGenerator()

    diff = {
        "values_changed": {
            "root['grantTypes']": {
                "old_value": ["authorization_code"],
                "new_value": ["authorization_code", "client_credentials"],
            }
        }
    }

    item = make_item("client1", "Client One", diff)

    insights = gen.generate_key_insights(
        command_name="oauth",
        added_items=[],
        modified_items=[item],
        removed_items=[],
    )

    assert any("grantTypes updated" in line for line in insights)
    assert "client1" in "".join(insights)


def test_oauth_redirect_uri_insight():
    gen = InsightsGenerator()

    diff = {"iterable_item_added": ["root['redirectionUris'][0]"]}

    item = make_item("client2", "Client Two", diff)

    insights = gen.generate_key_insights(
        command_name="oauth",
        added_items=[],
        modified_items=[item],
        removed_items=[],
    )

    assert any("redirectionUris updated" in line for line in insights)
    assert "client2" in "".join(insights)


def test_journeys_nodes_insight():
    gen = InsightsGenerator()

    diff = {
        "values_changed": {"root['nodes'][0]['id']": {"old_value": 1, "new_value": 2}}
    }

    item = make_item("journey1", "Journey One", diff)

    insights = gen.generate_key_insights(
        command_name="journeys",
        added_items=[],
        modified_items=[item],
        removed_items=[],
    )

    assert any("Authentication flow updated" in line for line in insights)
    assert "journey1" in "".join(insights)


def test_managed_schema_property_changes():
    gen = InsightsGenerator()

    diff = {
        "values_changed": {
            "root['schema']['properties']['email']['type']": {
                "old_value": "string",
                "new_value": "object",
            }
        },
        "dictionary_item_added": {"root['schema']['properties']['phone']": {}},
        "dictionary_item_removed": {"root['schema']['properties']['age']": {}},
    }

    item = make_item("user", "User", diff)

    insights = gen.generate_key_insights(
        command_name="managed",
        added_items=[],
        modified_items=[item],
        removed_items=[],
    )

    combined = "".join(insights)

    assert "schema updates across properties" in combined
    assert "email" in combined
    assert "phone" in combined
    assert "age" in combined
