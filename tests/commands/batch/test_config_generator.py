import json
import pytest
import typer
from pathlib import Path

# ✅ Adjust if needed
from trxo.commands.batch.config_generator import create_config_generator_command


@pytest.fixture
def mock_console(monkeypatch):
    calls = {"info": [], "success": []}

    monkeypatch.setattr(
        "trxo.commands.batch.config_generator.info",
        lambda m: calls["info"].append(m),
    )
    monkeypatch.setattr(
        "trxo.commands.batch.config_generator.success",
        lambda m: calls["success"].append(m),
    )

    return calls


def test_generate_import_config_default(tmp_path, mock_console):
    """Test generation of default import configuration."""
    out = tmp_path / "cfg.json"

    gen = create_config_generator_command()
    gen(output_file=str(out), template_type="import", include_all=False)

    data = json.loads(out.read_text())
    assert data["description"] == "Batch import configuration"
    assert "imports" in data
    assert len(data["imports"]) == 3

    assert any("Generated import config" in m for m in mock_console["success"])
    assert any("batch import config" in m for m in mock_console["info"])


def test_generate_import_config_all(tmp_path, mock_console):
    """Test generation of import configuration including all commands."""
    out = tmp_path / "cfg.json"

    gen = create_config_generator_command()
    gen(output_file=str(out), template_type="import", include_all=True)

    data = json.loads(out.read_text())
    assert len(data["imports"]) > 3
    commands = {i["command"] for i in data["imports"]}
    assert "authn" in commands
    assert "services" in commands


def test_generate_export_config_default(tmp_path, mock_console):
    """Test generation of default export configuration."""
    out = tmp_path / "cfg.json"

    gen = create_config_generator_command()
    gen(output_file=str(out), template_type="export", include_all=False)

    data = json.loads(out.read_text())
    assert data["description"] == "Batch export configuration"
    assert data["exports"]["output_dir"] == "batch_exports"
    assert data["exports"]["commands"] == [
        "realms",
        "services",
        "themes",
        "managed",
    ]


def test_generate_export_config_all(tmp_path, mock_console):
    """Test generation of export configuration including all commands."""
    out = tmp_path / "cfg.json"

    gen = create_config_generator_command()
    gen(output_file=str(out), template_type="export", include_all=True)

    data = json.loads(out.read_text())
    assert "realms" in data["exports"]["commands"]
    assert "connectors" in data["exports"]["commands"]


def test_invalid_template_type_raises(tmp_path, mock_console):
    """Test error when template type is invalid."""
    out = tmp_path / "cfg.json"

    gen = create_config_generator_command()

    with pytest.raises(typer.Exit):
        gen(output_file=str(out), template_type="nope", include_all=False)
