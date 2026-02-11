import os
from pathlib import Path
from datetime import datetime, timedelta

from trxo.logging.utils import (
    sanitize_data,
    sanitize_dict,
    sanitize_list,
    sanitize_string,
    format_size,
    cleanup_old_logs,
    get_log_directory,
)


def test_sanitize_dict_masks_sensitive_key():
    data = {"token": "supersecret", "name": "john"}
    result = sanitize_dict(data, ("token",))

    assert result["token"] != "supersecret"
    assert result["name"] == "john"


def test_sanitize_list_masks_nested_data():
    data = [{"password": "secret"}, {"x": 1}]
    result = sanitize_list(data, ("password",))

    assert result[0]["password"] != "secret"
    assert result[1]["x"] == 1


def test_sanitize_data_handles_string_patterns():
    text = "Bearer abcdefghijklmnop"
    result = sanitize_data(text, ("token",))

    assert "Bearer ***" in result


def test_sanitize_string_url_token():
    url = "https://example.com?token=abcdef"
    result = sanitize_string(url, ("token",))

    assert "token=***" in result


def test_format_size_bytes():
    assert format_size(512) == "512B"


def test_format_size_kb():
    assert format_size(1024) == "1.0KB"


def test_format_size_mb():
    assert format_size(1024 * 1024) == "1.0MB"


def test_cleanup_old_logs_removes_old_files(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    old_file = log_dir / "trxo.log.1"
    new_file = log_dir / "trxo.log.2"

    old_file.write_text("old")
    new_file.write_text("new")

    old_time = (datetime.now() - timedelta(days=40)).timestamp()
    new_time = (datetime.now() - timedelta(days=1)).timestamp()

    os.utime(old_file, (old_time, old_time))
    os.utime(new_file, (new_time, new_time))

    removed = cleanup_old_logs(log_dir, retention_days=30)

    assert removed == 1
    assert not old_file.exists()
    assert new_file.exists()


def test_cleanup_old_logs_no_dir(tmp_path):
    removed = cleanup_old_logs(tmp_path / "missing", retention_days=30)
    assert removed == 0


def test_get_log_directory_delegates_to_config(mocker, tmp_path):
    mocker.patch(
        "trxo.logging.config.get_log_directory",
        return_value=tmp_path,
    )

    result = get_log_directory()
    assert result == tmp_path
