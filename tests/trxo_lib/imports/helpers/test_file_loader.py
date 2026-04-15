import json
from unittest.mock import MagicMock

import pytest

from trxo_lib.imports.helpers.file_loader import FileLoader


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
        FileLoader.load_from_local_file("missing.json")


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

    mocker.patch("trxo_lib.imports.helpers.file_loader.logger.error")

    result = FileLoader.load_from_git_file(file)

    assert result == []


# -------------------------
# Git discovery tests
# -------------------------


def test_discover_git_files_with_realm(tmp_path, mocker):
    repo = tmp_path
    f1 = repo / "a.json"
    f1.write_text("{}")

    # Mock the discovery method
    mocker.patch(
        "trxo_lib.imports.helpers.file_loader.FileLoader.discover_git_files",
        return_value=[f1],
    )

    result = FileLoader.discover_git_files(repo, "scripts", "alpha")

    assert result == [f1]


def test_discover_git_files_component_not_found(tmp_path):
    result = FileLoader.discover_git_files(tmp_path, "scripts", "alpha")

    assert result == []


# -------------------------
# Git loading tests
# -------------------------


def test_load_git_files_happy_path(tmp_path, mocker):
    repo = tmp_path

    f1 = repo / "a.json"
    f1.write_text(json.dumps({"data": {"result": [{"x": 1}]}}))

    git_manager = MagicMock()
    git_manager.local_path = repo

    mocker.patch(
        "trxo_lib.imports.helpers.file_loader.FileLoader.discover_git_files",
        return_value=[f1],
    )

    mocker.patch("trxo_lib.imports.helpers.file_loader.logger.info")

    result = FileLoader.load_git_files(git_manager, "scripts", "alpha")

    assert result == [{"x": 1}]


def test_load_git_files_empty_result(tmp_path):
    git_manager = MagicMock()
    git_manager.local_path = tmp_path

    result = FileLoader.load_git_files(git_manager, "scripts", "alpha")

    assert result == []


def test_load_git_files_partial_failure(tmp_path, mocker):
    repo = tmp_path

    good = repo / "good.json"
    bad = repo / "bad.json"

    good.write_text(json.dumps({"data": {"result": [{"x": 1}]}}))
    bad.write_text("{ bad json")

    git_manager = MagicMock()
    git_manager.local_path = repo

    mocker.patch(
        "trxo_lib.imports.helpers.file_loader.FileLoader.discover_git_files",
        return_value=[good, bad],
    )

    mocker.patch("trxo_lib.imports.helpers.file_loader.logger.info")
    mocker.patch("trxo_lib.imports.helpers.file_loader.logger.warning")

    result = FileLoader.load_git_files(git_manager, "scripts", "alpha")

    assert result == [{"x": 1}]
