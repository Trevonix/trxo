import os
from pathlib import Path

import pytest

from trxo.logging.config import (
    LogLevel,
    LogConfig,
    get_log_directory,
    get_log_file_path,
)


def test_log_level_values():
    assert LogLevel.DEBUG.value == "DEBUG"
    assert LogLevel.INFO.value == "INFO"
    assert LogLevel.WARNING.value == "WARNING"
    assert LogLevel.ERROR.value == "ERROR"


def test_log_config_defaults():
    cfg = LogConfig()

    assert cfg.default_level == LogLevel.DEBUG
    assert cfg.console_level == LogLevel.WARNING
    assert cfg.log_api_requests is True
    assert cfg.log_api_responses is True
    assert cfg.max_payload_size == 1024


def test_get_log_directory_windows(mocker, tmp_path):
    mocker.patch("platform.system", return_value="Windows")
    mocker.patch.dict(os.environ, {"APPDATA": str(tmp_path)})
    log_dir = get_log_directory()

    assert log_dir.exists()
    assert log_dir.name == "logs"


def test_get_log_directory_windows_fallback_home(mocker, tmp_path):
    mocker.patch("platform.system", return_value="Windows")
    mocker.patch.dict(os.environ, {"APPDATA": ""})
    mocker.patch("pathlib.Path.home", return_value=tmp_path)

    log_dir = get_log_directory()

    assert log_dir.exists()
    assert log_dir.name == "logs"


def test_get_log_directory_macos(mocker, tmp_path):
    mocker.patch("platform.system", return_value="Darwin")
    mocker.patch("pathlib.Path.home", return_value=tmp_path)

    log_dir = get_log_directory()

    assert log_dir.exists()
    assert "Library" in str(log_dir)


def test_get_log_directory_linux_with_xdg(mocker, tmp_path):
    mocker.patch("platform.system", return_value="Linux")
    mocker.patch.dict(os.environ, {"XDG_DATA_HOME": str(tmp_path)})

    log_dir = get_log_directory()

    assert log_dir.exists()
    assert log_dir.name == "logs"


def test_get_log_directory_linux_fallback_home(mocker, tmp_path):
    mocker.patch("platform.system", return_value="Linux")
    mocker.patch.dict(os.environ, {"XDG_DATA_HOME": ""})
    mocker.patch("pathlib.Path.home", return_value=tmp_path)

    log_dir = get_log_directory()

    assert log_dir.exists()
    assert log_dir.name == "logs"


def test_get_log_directory_permission_error_fallback(mocker, tmp_path):
    mocker.patch("platform.system", return_value="Linux")
    mocker.patch("pathlib.Path.home", return_value=tmp_path)

    real_mkdir = Path.mkdir
    mkdir_calls = {"count": 0}

    def mkdir_side_effect(self, *args, **kwargs):
        mkdir_calls["count"] += 1
        if mkdir_calls["count"] == 1:
            raise PermissionError("no permission")
        return real_mkdir(self, *args, **kwargs)

    mocker.patch("pathlib.Path.mkdir", new=mkdir_side_effect)
    mocker.patch("pathlib.Path.cwd", return_value=tmp_path)

    log_dir = get_log_directory()

    assert log_dir.exists()
    assert log_dir.name == "logs"


def test_get_log_file_path_default_config(mocker, tmp_path):
    mocker.patch("trxo.logging.config.get_log_directory", return_value=tmp_path)

    path = get_log_file_path()

    assert path.parent == tmp_path
    assert path.name.endswith(".log")


def test_get_log_file_path_custom_config(mocker, tmp_path):
    mocker.patch("trxo.logging.config.get_log_directory", return_value=tmp_path)

    cfg = LogConfig(log_filename="custom.log")
    path = get_log_file_path(cfg)

    assert path.name == "custom.log"
