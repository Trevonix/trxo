import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from trxo.utils.export.file_saver import FileSaver

def test_build_versioned_filename():
    # Test without realm prefix
    fn1 = FileSaver.build_versioned_filename("cmd", None, "v1", "2023")
    assert fn1 == "cmd_v1_2023.json"
    
    # Test with realm prefix
    fn2 = FileSaver.build_versioned_filename("cmd", "alpha", "v2", "2024")
    assert fn2 == "alpha_cmd_v2_2024.json"

def test_determine_next_version_fallback(tmp_path):
    # Create some files to simulate existing versions
    (tmp_path / "test_v1_20230101_100000.json").write_text("{}")
    (tmp_path / "test_v5_20230101_110000.json").write_text("{}")
    (tmp_path / "other_v10_2023.json").write_text("{}")
    
    # Should find max version 5 and return 6
    next_v = FileSaver.determine_next_version(str(tmp_path), "test")
    assert next_v == 6

def test_determine_next_version_empty_dir(tmp_path):
    next_v = FileSaver.determine_next_version(str(tmp_path), "new_component")
    assert next_v == 1

def test_save_with_progress_success(tmp_path, mocker):
    mocker.patch("trxo.utils.export.file_saver.info")
    mocker.patch("time.sleep") # Speed up tests
    
    file_path = tmp_path / "test.json"
    data = {"key": "value"}
    
    success = FileSaver.save_with_progress(data, file_path, "test.json")
    
    assert success is True
    assert file_path.exists()
    assert json.loads(file_path.read_text()) == data

def test_save_with_progress_failure(tmp_path, mocker):
    mocker.patch("trxo.utils.export.file_saver.error")
    
    # Attempt to save to a directory path as if it were a file
    bad_path = tmp_path / "dir"
    bad_path.mkdir()
    
    success = FileSaver.save_with_progress({}, bad_path, "fail.json")
    assert success is False

def test_save_to_local_no_version(tmp_path, mocker):
    mocker.patch("trxo.utils.export.file_saver.FileSaver.save_with_progress", return_value=True)
    
    data = {"metadata": {"realm": "alpha"}}
    path = FileSaver.save_to_local(
        data, "saml", output_dir=str(tmp_path), no_version=True
    )
    
    assert path is not None
    assert "alpha_saml_" in path
    assert data["metadata"]["version"] == "saml"

def test_save_to_local_custom_version(tmp_path, mocker):
    mocker.patch("trxo.utils.export.file_saver.FileSaver.save_with_progress", return_value=True)
    
    data = {}
    path = FileSaver.save_to_local(
        data, "saml", output_dir=str(tmp_path), version="my-v1"
    )
    
    assert "saml_my-v1_" in path
    assert data["metadata"]["version"] == "my-v1"

def test_save_to_local_auto_version(tmp_path, mocker):
    mocker.patch("trxo.utils.export.file_saver.FileSaver.save_with_progress", return_value=True)
    mocker.patch("trxo.utils.export.file_saver.FileSaver.determine_next_version", return_value=3)
    
    data = {}
    path = FileSaver.save_to_local(data, "saml", output_dir=str(tmp_path))
    
    assert "saml_v3_" in path
    assert data["metadata"]["version"] == "v3"

def test_save_to_local_special_commands(tmp_path, mocker):
    mocker.patch("trxo.utils.export.file_saver.FileSaver.save_with_progress", return_value=True)
    
    # Test services_realm_...
    data = {}
    path = FileSaver.save_to_local(data, "services_realm_alpha", output_dir=str(tmp_path))
    assert "alpha_services_v1_" in path
    
    # Test services_global
    path = FileSaver.save_to_local(data, "services_global", output_dir=str(tmp_path))
    assert "services_v1_" in path

def test_save_to_local_failure(mocker):
    mocker.patch("trxo.utils.export.file_saver.FileSaver.save_with_progress", return_value=False)
    
    path = FileSaver.save_to_local({}, "saml")
    assert path is None
