import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from trxo.utils.export.file_saver import FileSaver


def test_build_versioned_filename_with_realm():
    filename = FileSaver.build_versioned_filename(
        command_name="journeys",
        realm_prefix="alpha",
        version_tag="v1",
        timestamp="20260101_120000",
    )
    assert filename == "alpha_journeys_v1_20260101_120000.json"


def test_build_versioned_filename_without_realm():
    filename = FileSaver.build_versioned_filename(
        command_name="journeys",
        realm_prefix=None,
        version_tag="v2",
        timestamp="20260101_120000",
    )
    assert filename == "journeys_v2_20260101_120000.json"


def test_determine_next_version_fallback(tmp_path, mocker):
    mocker.patch.dict("sys.modules", {"py_file_versioning": None})

    (tmp_path / "alpha_journeys_v1_20260101.json").write_text("{}")
    (tmp_path / "alpha_journeys_v2_20260102.json").write_text("{}")

    next_version = FileSaver.determine_next_version(str(tmp_path), "alpha_journeys")

    assert next_version == 3


def test_save_with_progress_success(tmp_path, mocker):
    data = {"a": 1}
    file_path = tmp_path / "test.json"

    fake_pbar = MagicMock()
    mocker.patch("trxo.utils.export.file_saver.tqdm", return_value=fake_pbar)
    mocker.patch("trxo.utils.export.file_saver.time.sleep")
    mocker.patch("trxo.utils.export.file_saver.info")

    ok = FileSaver.save_with_progress(data, file_path, "test.json")

    assert ok is True
    assert file_path.exists()

    saved = json.loads(file_path.read_text(encoding="utf-8"))
    assert saved == data


def test_save_with_progress_failure(tmp_path, mocker):
    data = {"a": 1}
    file_path = tmp_path / "test.json"

    mocker.patch("trxo.utils.export.file_saver.tqdm", side_effect=Exception("boom"))
    mocker.patch("trxo.utils.export.file_saver.error")

    ok = FileSaver.save_with_progress(data, file_path, "test.json")

    assert ok is False


def test_save_to_local_basic(tmp_path, mocker):
    data = {"items": [1, 2, 3], "metadata": {"realm": "alpha"}}

    mocker.patch(
        "trxo.utils.export.file_saver.FileSaver.save_with_progress",
        return_value=True,
    )

    path = FileSaver.save_to_local(
        data=data,
        command_name="journeys",
        output_dir=str(tmp_path),
    )

    assert path is not None
    saved_path = Path(path)
    assert saved_path.suffix == ".json"
    assert "alpha_journeys" in saved_path.name
    assert "version" in data["metadata"]
