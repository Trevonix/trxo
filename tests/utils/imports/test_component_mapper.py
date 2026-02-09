import pytest

from trxo.utils.imports.component_mapper import ComponentMapper


def test_get_component_directory_direct_mapping():
    assert ComponentMapper.get_component_directory("scripts") == "scripts"


def test_get_component_directory_descriptive_mapping():
    assert (
        ComponentMapper.get_component_directory("Email Templates") == "email_templates"
    )


def test_get_component_directory_case_sensitive_key():
    assert ComponentMapper.get_component_directory("Themes") == "themes"


def test_get_component_directory_dynamic_parentheses_mapping():
    assert ComponentMapper.get_component_directory("policies (alpha)") == "policies"


def test_get_component_directory_dynamic_unknown_base():
    assert ComponentMapper.get_component_directory("unknown (realm)") == "unknown"


def test_get_component_directory_fallback_unknown():
    assert (
        ComponentMapper.get_component_directory("some_random_type")
        == "some_random_type"
    )


def test_get_command_name_direct_mapping():
    assert ComponentMapper.get_command_name("scripts") == "scripts"


def test_get_command_name_descriptive_mapping():
    assert ComponentMapper.get_command_name("authentication settings") == "authn"


def test_get_command_name_parentheses_removed():
    assert ComponentMapper.get_command_name("webhooks (alpha)") == "webhooks"


def test_get_command_name_known_parenthesized_mapping():
    assert ComponentMapper.get_command_name("policies (alpha)") == "policies"


def test_get_command_name_unknown_fallback_snake_case():
    assert ComponentMapper.get_command_name("My Custom Type") == "my_custom_type"


def test_get_command_name_preserves_underscores():
    assert ComponentMapper.get_command_name("managed_objects") == "managed"


def test_get_command_name_trim_spaces():
    assert ComponentMapper.get_command_name("   scripts   ") == "scripts"


def test_is_root_level_component_true():
    assert ComponentMapper.is_root_level_component("Applications") is True


def test_is_root_level_component_false():
    assert ComponentMapper.is_root_level_component("scripts") is False


def test_is_root_level_component_case_sensitive():
    assert ComponentMapper.is_root_level_component("applications") is False


def test_is_root_level_component_unknown():
    assert ComponentMapper.is_root_level_component("unknown") is False


def test_empty_string_component_directory():
    assert ComponentMapper.get_component_directory("") == ""


def test_empty_string_command_name():
    assert ComponentMapper.get_command_name("") == ""


def test_only_parentheses_command_name():
    assert ComponentMapper.get_command_name("(alpha)") == ""


def test_only_parentheses_component_directory():
    assert ComponentMapper.get_component_directory("(alpha)") == ""


def test_numeric_type_fallback():
    assert ComponentMapper.get_command_name("123") == "123"


def test_special_characters_fallback():
    assert ComponentMapper.get_command_name("@@@ ###") == "@@@_###"
