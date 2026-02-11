import json
import pytest
from types import SimpleNamespace
import typer

from trxo.commands.batch.batch_import import (
    create_batch_import_command,
    _get_storage_mode,
    _load_config_file_imports,
    _find_file_for_command,
    _get_search_patterns,
    _extract_version_number,
)


@pytest.fixture
def mock_console(monkeypatch):
    calls = {"info": [], "success": [], "error": [], "warning": []}

    monkeypatch.setattr(
        "trxo.commands.batch.batch_import.info", lambda m: calls["info"].append(m)
    )
    monkeypatch.setattr(
        "trxo.commands.batch.batch_import.success", lambda m: calls["success"].append(m)
    )
    monkeypatch.setattr(
        "trxo.commands.batch.batch_import.error", lambda m: calls["error"].append(m)
    )
    monkeypatch.setattr(
        "trxo.commands.batch.batch_import.warning", lambda m: calls["warning"].append(m)
    )

    return calls


@pytest.fixture
def mock_config_store_local(monkeypatch):
    class MockConfigStore:
        def get_current_project(self):
            return "proj"

        def get_project_config(self, name):
            return {"storage_mode": "local"}

    monkeypatch.setattr(
        "trxo.commands.batch.batch_import.ConfigStore",
        lambda: MockConfigStore(),
    )


@pytest.fixture
def mock_config_store_git(monkeypatch):
    class MockConfigStore:
        def get_current_project(self):
            return "proj"

        def get_project_config(self, name):
            return {"storage_mode": "git"}

    monkeypatch.setattr(
        "trxo.commands.batch.batch_import.ConfigStore",
        lambda: MockConfigStore(),
    )


@pytest.fixture
def mock_import_app(monkeypatch):
    class MockCommand:
        def __init__(self, should_fail=False):
            self.should_fail = should_fail
            self.calls = []

        def callback(self, **kwargs):
            self.calls.append(kwargs)
            if self.should_fail:
                raise RuntimeError("boom")

    class MockGroup:
        def __init__(self, fail=False):
            self.commands = {
                "gateway": MockCommand(fail),
                "secrets": MockCommand(fail),
            }

    app = SimpleNamespace(
        commands={
            "realms": MockCommand(),
            "services": MockCommand(),
            "agent": MockGroup(),
            "esv": MockGroup(),
        }
    )

    monkeypatch.setattr(
        "trxo.commands.batch.batch_import.typer.main.get_command",
        lambda _: app,
    )

    return app


def test_get_storage_mode_fallback():
    class BadStore:
        def get_current_project(self):
            raise RuntimeError("boom")

    assert _get_storage_mode(BadStore()) == "local"


def test_load_config_file_imports_invalid_json(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text("{bad")

    with pytest.raises(typer.Exit):
        _load_config_file_imports(str(f))


def test_load_config_file_imports_missing_imports(tmp_path):
    f = tmp_path / "cfg.json"
    f.write_text(json.dumps({}))

    with pytest.raises(typer.Exit):
        _load_config_file_imports(str(f))


def test_extract_version_number_edge_cases():
    assert _extract_version_number("file_v001_export.json") == 1
    assert _extract_version_number("file_export.json") == 0
    assert _extract_version_number("file_v99_.json") == 99


def test_get_search_patterns_variants():
    p = _get_search_patterns("agent.gateway")
    assert "agent_gateway" in p
    assert "agents_gateway" in p
    assert "gateway_agent" in p


def test_find_file_for_command_multiple(monkeypatch, tmp_path):
    f1 = tmp_path / "realms_v1_export.json"
    f2 = tmp_path / "realms_v2_export.json"
    f1.write_text("{}")
    f2.write_text("{}")

    monkeypatch.setattr(
        "trxo.commands.batch.batch_import._prompt_user_file_choice",
        lambda c, f: f2,
    )

    result = _find_file_for_command("realms", tmp_path)
    assert result == f2


def test_batch_import_local_success(
    tmp_path, mock_console, mock_config_store_local, mock_import_app
):
    f = tmp_path / "realms_export.json"
    f.write_text("{}")

    batch_import = create_batch_import_command()
    batch_import(commands=["realms"], dir=str(tmp_path), config_file=None)

    assert any(
        "all imports completed successfully" in m.lower()
        for m in mock_console["success"]
    )


def test_batch_import_dry_run(
    tmp_path, mock_console, mock_config_store_local, mock_import_app
):
    f = tmp_path / "realms_export.json"
    f.write_text("{}")

    batch_import = create_batch_import_command()
    batch_import(commands=["realms"], dir=str(tmp_path), dry_run=True, config_file=None)

    assert any("dry run" in m.lower() for m in mock_console["info"])


def test_batch_import_missing_dir(
    mock_console, mock_config_store_local, mock_import_app
):
    batch_import = create_batch_import_command()

    with pytest.raises(typer.Exit):
        batch_import(commands=["realms"], dir="no_such_dir", config_file=None)

    assert mock_console["error"]


def test_batch_import_git_mode(mock_console, mock_config_store_git, mock_import_app):
    batch_import = create_batch_import_command()
    batch_import(commands=["realms"], dir=None, config_file=None)

    assert any("git storage mode" in m.lower() for m in mock_console["info"])


def test_batch_import_continue_on_error(
    tmp_path, mock_console, mock_config_store_local, monkeypatch
):
    f = tmp_path / "realms_export.json"
    f.write_text("{}")

    class FailingCmd:
        def callback(self, **kwargs):
            raise RuntimeError("boom")

    app = SimpleNamespace(commands={"realms": FailingCmd()})
    monkeypatch.setattr(
        "trxo.commands.batch.batch_import.typer.main.get_command",
        lambda _: app,
    )

    batch_import = create_batch_import_command()
    batch_import(
        commands=["realms"],
        dir=str(tmp_path),
        continue_on_error=True,
        config_file=None,
    )

    assert any("successful:" in m.lower() for m in mock_console["info"])
