import pytest
from trxo_lib.logging.utils import sanitize_data, format_size

def test_sanitize_dict():
    sensitive_keys = ("password", "token", "secret")
    data = {
        "username": "user1",
        "password": "my_secret_password",
        "nested": {
            "token": "long_bearer_token_string",
            "other": "value"
        },
        "list": [{"secret": "s1"}, "normal"]
    }
    sanitized = sanitize_data(data, sensitive_keys)
    assert sanitized["username"] == "user1"
    assert sanitized["password"] == "my_s...word"
    assert sanitized["nested"]["token"] == "long...ring"
    assert sanitized["list"][0]["secret"] == "***"
    assert sanitized["list"][1] == "normal"

def test_sanitize_string():
    sensitive_keys = ("token",)
    url = "http://api.com?token=12345&user=me"
    sanitized = sanitize_data(url, sensitive_keys)
    assert "token=***" in sanitized
    assert "user=me" in sanitized
    
    bearer = "Authorization: Bearer my-token"
    assert "Bearer ***" in sanitize_data(bearer, sensitive_keys)

def test_format_size():
    assert format_size(500) == "500B"
    assert format_size(1500) == "1.5KB"
    assert format_size(2 * 1024 * 1024) == "2.0MB"
    assert format_size(3 * 1024 * 1024 * 1024) == "3.0GB"

def test_sanitize_other_types():
    assert sanitize_data(123, ()) == 123
    assert sanitize_data(None, ()) is None
