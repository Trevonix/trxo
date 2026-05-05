import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
import typer
from trxo.commands.batch.batch_import import (
    _extract_version_number,
    _find_file_for_command,
    _get_search_patterns,
    _get_storage_mode,
    _load_config_file_imports,
    create_batch_import_command,
)

# Helper to call batch_import with explicit defaults to avoid Typer object injection
def call_batch_import(func, **kwargs):
    defaults = {
        "commands": None,
        "dir": None,
        "config_file": None,
        "scope": "realm",
        "realm": "root",
        "branch": None,
        "jwk_path": None,
        "sa_id": None,
        "base_url": None,
        "project_name": None,
        "auth_mode": None,
        "onprem_username": None,
        "onprem_password": None,
        "onprem_realm": "root",
        "am_base_url": None,
        "idm_base_url": None,
        "idm_username": None,
        "idm_password": None,
        "continue_on_error": True,
        "dry_run": False,
        "force_import": False,
        "diff": False,
    }
    defaults.update(kwargs)
    return func(**defaults)

@pytest.fixture
def mock_console(mocker):
    calls = {"info": [], "success": [], "error": [], "warning": []}
    mocker.patch("trxo.commands.batch.batch_import.info", side_effect=lambda m: calls["info"].append(m))
    mocker.patch("trxo.commands.batch.batch_import.success", side_effect=lambda m: calls["success"].append(m))
    mocker.patch("trxo.commands.batch.batch_import.error", side_effect=lambda m: calls["error"].append(m))
    mocker.patch("trxo.commands.batch.batch_import.warning", side_effect=lambda m: calls["warning"].append(m))
    return calls

@pytest.fixture
def mock_config_store_local(mocker):
    mock_store = mocker.Mock()
    mock_store.get_current_project.return_value = "proj"
    mock_store.get_project_config.return_value = {"storage_mode": "local"}
    mocker.patch("trxo.commands.batch.batch_import.ConfigStore", return_value=mock_store)
    return mock_store

@pytest.fixture
def mock_config_store_git(mocker):
    mock_store = mocker.Mock()
    mock_store.get_current_project.return_value = "proj"
    mock_store.get_project_config.return_value = {"storage_mode": "git"}
    mocker.patch("trxo.commands.batch.batch_import.ConfigStore", return_value=mock_store)
    return mock_store

@pytest.fixture
def mock_import_app(mocker):
    mock_app = mocker.Mock()
    mock_realms = mocker.Mock()
    mock_services = mocker.Mock()
    mock_agent = mocker.Mock()
    mock_gateway = mocker.Mock()
    mock_agent.commands = {"gateway": mock_gateway}
    mock_app.commands = {
        "realms": mock_realms,
        "services": mock_services,
        "agent": mock_agent
    }
    # Patch in multiple places to be sure
    mocker.patch("trxo.commands.batch.batch_import.typer.main.get_command", return_value=mock_app)
    mocker.patch("typer.main.get_command", return_value=mock_app)
    return mock_app

def test_get_storage_mode_fallback(mocker):
    mock_store = mocker.Mock()
    mock_store.get_current_project.side_effect = RuntimeError("boom")
    assert _get_storage_mode(mock_store) == "local"

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

def test_find_file_for_command_multiple(mocker, tmp_path):
    f1 = tmp_path / "realms_v1_export.json"
    f2 = tmp_path / "realms_v2_export.json"
    f1.write_text("{}")
    f2.write_text("{}")
    mocker.patch("trxo.commands.batch.batch_import._prompt_user_file_choice", return_value=f2)
    result = _find_file_for_command("realms", tmp_path)
    assert result == f2

def test_batch_import_local_success(tmp_path, mock_console, mock_config_store_local, mock_import_app):
    f = tmp_path / "realms_export.json"
    f.write_text("{}")
    batch_import = create_batch_import_command()
    call_batch_import(batch_import, commands=["realms"], dir=str(tmp_path))
    assert any("completed successfully" in m.lower() for m in mock_console["success"])
    assert mock_import_app.commands["realms"].callback.called

def test_batch_import_dry_run(tmp_path, mock_console, mock_config_store_local, mock_import_app):
    f = tmp_path / "realms_export.json"
    f.write_text("{}")
    batch_import = create_batch_import_command()
    call_batch_import(batch_import, commands=["realms"], dir=str(tmp_path), dry_run=True)
    assert any("dry run" in m.lower() for m in mock_console["info"])
    assert not mock_import_app.commands["realms"].callback.called

def test_batch_import_missing_dir(mock_console, mock_config_store_local, mock_import_app):
    batch_import = create_batch_import_command()
    with pytest.raises((typer.Exit, SystemExit)):
        call_batch_import(batch_import, commands=["realms"], dir="no_such_dir")
    assert any("not found" in m.lower() for m in mock_console["error"])

def test_batch_import_git_mode(mock_console, mock_config_store_git, mock_import_app):
    batch_import = create_batch_import_command()
    call_batch_import(batch_import, commands=["realms"])
    assert any("git storage mode" in m.lower() for m in mock_console["info"])
    assert mock_import_app.commands["realms"].callback.called

def test_batch_import_continue_on_error(tmp_path, mock_console, mock_config_store_local, mocker):
    f = tmp_path / "realms_export.json"
    f.write_text("{}")
    mock_app = mocker.Mock()
    mock_realms = mocker.Mock()
    mock_realms.callback.side_effect = RuntimeError("boom")
    mock_app.commands = {"realms": mock_realms}
    mocker.patch("trxo.commands.batch.batch_import.typer.main.get_command", return_value=mock_app)
    
    batch_import = create_batch_import_command()
    with pytest.raises((Exception, SystemExit)):
        call_batch_import(batch_import, commands=["realms"], dir=str(tmp_path), continue_on_error=True)
    assert any("successful: 0/1" in m.lower() for m in mock_console["info"])

def test_batch_import_explicit_file(tmp_path, mock_console, mock_config_store_local, mock_import_app):
    f = tmp_path / "custom.json"
    f.write_text("{}")
    batch_import = create_batch_import_command()
    call_batch_import(batch_import, commands=["realms:custom.json"], dir=str(tmp_path))
    assert mock_import_app.commands["realms"].callback.called

def test_batch_import_config_file_success(tmp_path, mock_console, mock_config_store_local, mock_import_app):
    f = tmp_path / "realms_export.json"
    f.write_text("{}")
    cfg = tmp_path / "batch.json"
    cfg.write_text(json.dumps({"imports": [{"command": "realms", "file": str(f)}]}))
    batch_import = create_batch_import_command()
    call_batch_import(batch_import, config_file=str(cfg), dir=str(tmp_path))
    assert mock_import_app.commands["realms"].callback.called

def test_batch_import_stop_on_error(tmp_path, mock_console, mock_config_store_local, mocker):
    f = tmp_path / "realms_export.json"
    f.write_text("{}")
    mock_app = mocker.Mock()
    mock_realms = mocker.Mock()
    mock_realms.callback.side_effect = RuntimeError("boom")
    mock_app.commands = {"realms": mock_realms}
    mocker.patch("trxo.commands.batch.batch_import.typer.main.get_command", return_value=mock_app)
    
    batch_import = create_batch_import_command()
    with pytest.raises((Exception, SystemExit)):
        call_batch_import(batch_import, commands=["realms"], dir=str(tmp_path), continue_on_error=False)

def test_prompt_user_file_choice_skip(mocker):
    import trxo.commands.batch.batch_import as mod
    files = [Path("f1_v1_.json"), Path("f1_v2_.json")]
    mocker.patch("typer.prompt", return_value="s")
    res = mod._prompt_user_file_choice("cmd", files)
    assert res is None

def test_prompt_user_file_choice_valid_index(mocker):
    import trxo.commands.batch.batch_import as mod
    files = [Path("f1_v1_.json"), Path("f1_v2_.json")]
    mocker.patch("typer.prompt", return_value="1") 
    res = mod._prompt_user_file_choice("cmd", files)
    assert res.name == "f1_v2_.json"

def test_batch_import_service_scope(tmp_path, mock_console, mock_config_store_local, mock_import_app):
    f = tmp_path / "services_export.json"
    f.write_text("{}")
    batch_import = create_batch_import_command()
    call_batch_import(batch_import, commands=["services"], dir=str(tmp_path), scope="realm", realm="alpha")
    assert mock_import_app.commands["services"].callback.called
    kwargs = mock_import_app.commands["services"].callback.call_args[1]
    assert kwargs["scope"] == "realm"
    assert kwargs["realm"] == "alpha"

def test_batch_import_dot_notation(tmp_path, mock_console, mock_config_store_local, mock_import_app):
    f = tmp_path / "agents_gateway_export.json"
    f.write_text("{}")
    batch_import = create_batch_import_command()
    call_batch_import(batch_import, commands=["agent.gateway"], dir=str(tmp_path))
    assert mock_import_app.commands["agent"].commands["gateway"].callback.called
