import json
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from trxo.utils.imports.file_loader import FileLoader


def test_load_from_local_file_happy_path_collection(tmp_path):
    file = tmp_path / "data.json"
    file.write_text(json.dumps({"data": {"result": [{"_id": "1"}, {"_id": "2"}]}}))

    result = FileLoader.load_from_local_file(str(file))

    assert result == [{"_id": "1"}, {"_id": "2"}]


def test_load_from_local_file_single_object(tmp_path):
    file = tmp_path / "data.json"
    file.write_text(json.dumps({"data": {"_id": "1"}}))

    result = FileLoader.load_from_local_file(str(file))

    assert result == [{"_id": "1"}]


def test_load_from_local_file_missing_file():
    with pytest.raises(Exception):
        FileLoader.load_from_local_file("does_not_exist.json")


def test_load_from_local_file_invalid_json(tmp_path):
    file = tmp_path / "data.json"
    file.write_text("{ invalid json")

    with pytest.raises(ValueError):
        FileLoader.load_from_local_file(str(file))


def test_load_from_local_file_invalid_root_type(tmp_path):
    file = tmp_path / "data.json"
    file.write_text(json.dumps([1, 2, 3]))

    with pytest.raises(Exception):
        FileLoader.load_from_local_file(str(file))


def test_load_from_local_file_missing_data_key(tmp_path):
    file = tmp_path / "data.json"
    file.write_text(json.dumps({"x": 1}))

    with pytest.raises(Exception):
        FileLoader.load_from_local_file(str(file))


def test_load_from_git_file_happy_path_result(tmp_path):
    file = tmp_path / "a.json"
    file.write_text(json.dumps({"data": {"result": [{"x": 1}]}}))

    result = FileLoader.load_from_git_file(file)

    assert result == [{"x": 1}]


def test_load_from_git_file_direct_list(tmp_path):
    file = tmp_path / "a.json"
    file.write_text(json.dumps([{"x": 1}]))

    result = FileLoader.load_from_git_file(file)

    assert result == [{"x": 1}]


def test_load_from_git_file_direct_object(tmp_path):
    file = tmp_path / "a.json"
    file.write_text(json.dumps({"x": 1}))

    result = FileLoader.load_from_git_file(file)

    assert result == [{"x": 1}]


def test_load_from_git_file_invalid_json(tmp_path, mocker):
    file = tmp_path / "a.json"
    file.write_text("{ bad json")

    mocker.patch("trxo.utils.imports.file_loader.error")

    result = FileLoader.load_from_git_file(file)

    assert result == []


def test_discover_git_files_with_realm(tmp_path, mocker):
    repo = tmp_path
    realm_dir = repo / "alpha" / "scripts"
    realm_dir.mkdir(parents=True)
    f1 = realm_dir / "a.json"
    f1.write_text("{}")

    mocker.patch("trxo.utils.imports.file_loader.info")

    result = FileLoader.discover_git_files(repo, "scripts", "alpha")

    assert result == [f1]


def test_discover_git_files_all_realms(tmp_path, mocker):
    repo = tmp_path
    (repo / "alpha" / "scripts").mkdir(parents=True)
    (repo / "beta" / "scripts").mkdir(parents=True)

    f1 = repo / "alpha" / "scripts" / "a.json"
    f2 = repo / "beta" / "scripts" / "b.json"
    f1.write_text("{}")
    f2.write_text("{}")

    mocker.patch("trxo.utils.imports.file_loader.info")

    result = FileLoader.discover_git_files(repo, "scripts", None)

    assert set(result) == {f1, f2}


def test_discover_git_files_component_not_found(tmp_path):
    result = FileLoader.discover_git_files(tmp_path, "scripts", "alpha")
    assert result == []


def test_load_git_files_happy_path(tmp_path, mocker):
    repo = tmp_path
    (repo / "alpha" / "scripts").mkdir(parents=True)
    f1 = repo / "alpha" / "scripts" / "a.json"
    f1.write_text(json.dumps({"data": {"result": [{"x": 1}]}}))

    git_manager = MagicMock()
    git_manager.local_path = repo

    mocker.patch("trxo.utils.imports.file_loader.info")

    result = FileLoader.load_git_files(git_manager, "scripts", "alpha")

    assert result == [{"x": 1}]


def test_load_git_files_empty_result(tmp_path):
    git_manager = MagicMock()
    git_manager.local_path = tmp_path

    result = FileLoader.load_git_files(git_manager, "scripts", "alpha")

    assert result == []


def test_load_git_files_partial_failure(tmp_path, mocker):
    repo = tmp_path
    (repo / "alpha" / "scripts").mkdir(parents=True)
    good = repo / "alpha" / "scripts" / "a.json"
    bad = repo / "alpha" / "scripts" / "b.json"

    good.write_text(json.dumps({"data": {"result": [{"x": 1}]}}))
    bad.write_text("{ bad json")

    git_manager = MagicMock()
    git_manager.local_path = repo

    mocker.patch("trxo.utils.imports.file_loader.info")
    mocker.patch("trxo.utils.imports.file_loader.warning")

    result = FileLoader.load_git_files(git_manager, "scripts", "alpha")

    assert result == [{"x": 1}]
