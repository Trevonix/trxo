import json
import pytest
from types import SimpleNamespace
from pathlib import Path
import typer

from trxo.commands.batch.batch_import import (
    create_batch_import_command,
    _get_storage_mode,
    _load_config_file_imports,
    _build_command_imports,
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
def mock_config_store(monkeypatch):
    """Mock ConfigStore for testing."""

    class MockConfigStore:
        def get_current_project(self):
            return "proj"

        def get_project_config(self, name):
            return {"storage_mode": "local"}

    monkeypatch.setattr(
        "trxo.commands.batch.batch_import.ConfigStore",
        lambda: MockConfigStore(),
    )


def test_get_storage_mode_local():
    """Test that storage mode defaults to 'local'."""

    class MockConfigStore:
        def get_current_project(self):
            return None

    assert _get_storage_mode(MockConfigStore()) == "local"


def test_load_config_file_imports_success(tmp_path):
    """Test loading valid import configuration."""
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"imports": [{"command": "realms", "file": "a.json"}]}))

    imports = _load_config_file_imports(str(cfg))
    assert imports[0]["command"] == "realms"


def test_load_config_file_imports_missing_key(tmp_path):
    """Test error when configuration file is invalid."""
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({}))

    with pytest.raises(typer.Exit):
        _load_config_file_imports(str(cfg))


def test_build_command_imports_local_autodiscover(tmp_path):
    """Test auto-discovery of local import files."""
    f = tmp_path / "realms_export.json"
    f.write_text("{}")

    imports = _build_command_imports(["realms"], tmp_path, {"realms"}, "local")

    assert imports[0]["command"] == "realms"
    assert "realms_export.json" in imports[0]["file"]


def test_build_command_imports_git_mode():
    """Test that git mode does not require local files."""
    imports = _build_command_imports(["realms"], None, {"realms"}, "git")
    assert imports[0]["file"] is None


def test_find_file_for_command(tmp_path):
    """Test finding a file matching a command pattern."""
    f = tmp_path / "agents_gateway_export.json"
    f.write_text("{}")

    result = _find_file_for_command("agent.gateway", tmp_path)
    assert result.name == f.name


def test_get_search_patterns():
    """Test generation of file search patterns."""
    patterns = _get_search_patterns("agent.gateway")
    assert any("agent_gateway" in p for p in patterns)


def test_extract_version_number():
    """Test version number extraction from filenames."""
    assert _extract_version_number("realms_v12_export.json") == 12
    assert _extract_version_number("realms_export.json") == 0


def _mock_import_app(monkeypatch, fail=False):
    class MockCommand:
        def __init__(self, name, should_fail=False):
            self.name = name
            self.should_fail = should_fail

        def callback(self, **kwargs):
            if self.should_fail:
                raise RuntimeError("boom")

    class MockGroup:
        def __init__(self):
            self.commands = {
                "secrets": MockCommand("secrets"),
                "java": MockCommand("java"),
            }

    mock_app = SimpleNamespace(
        commands={
            "realms": MockCommand("realms", should_fail=fail),
            "services": MockCommand("services"),
            "esv": MockGroup(),
            "agent": MockGroup(),
        }
    )

    monkeypatch.setattr(
        "trxo.commands.batch.batch_import.typer.main.get_command",
        lambda _: mock_app,
    )

    return mock_app


def test_batch_import_success_local(
    tmp_path, mock_console, mock_config_store, monkeypatch
):
    """Test successful batch import in local mode."""
    f = tmp_path / "realms_export.json"
    f.write_text("{}")

    cfg = tmp_path / "batch_cfg.json"
    cfg.write_text(json.dumps({"imports": [{"command": "realms", "file": str(f)}]}))

    _mock_import_app(monkeypatch, fail=False)

    batch_import = create_batch_import_command()
    batch_import(config_file=str(cfg), dir=str(tmp_path))

    # We assert on user-visible behavior, not internal callback wiring
    assert any(
        "imported successfully" in m.lower() for m in mock_console["success"]
    ) or any("batch import summary" in m.lower() for m in mock_console["info"])


def test_batch_import_continue_on_error(
    tmp_path, mock_console, mock_config_store, monkeypatch
):
    """Test that import continues on error when requested."""
    f = tmp_path / "realms_export.json"
    f.write_text("{}")

    cfg = tmp_path / "batch_cfg.json"
    cfg.write_text(json.dumps({"imports": [{"command": "realms", "file": str(f)}]}))

    _mock_import_app(monkeypatch, fail=True)

    batch_import = create_batch_import_command()
    batch_import(config_file=str(cfg), dir=str(tmp_path), continue_on_error=True)

    # It should complete and print summary (no crash)
    assert any("batch import summary" in m.lower() for m in mock_console["info"])


def test_batch_import_stop_on_error(
    tmp_path, mock_console, mock_config_store, monkeypatch
):
    """Test that import stops on error by default."""
    f = tmp_path / "realms_export.json"
    f.write_text("{}")

    _mock_import_app(monkeypatch, fail=True)

    batch_import = create_batch_import_command()

    with pytest.raises(typer.Exit):
        batch_import(commands=["realms"], dir=str(tmp_path), continue_on_error=False)

    # At least one error should be logged before exit
    assert len(mock_console["error"]) > 0
