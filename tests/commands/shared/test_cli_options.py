import typer

from trxo.commands.shared.cli_options import (
    CommonOptions,
    create_auth_params,
    create_export_params,
    create_import_params,
)
from trxo.commands.shared.options import ContinueOnErrorOpt


def test_auth_options_contains_expected_keys():
    opts = CommonOptions.auth_options()

    assert "jwk_path" in opts
    assert "sa_id" in opts
    assert "base_url" in opts
    assert "am_base_url" in opts
    assert "project_name" in opts
    # client_id was removed in favour of sa_id only
    assert "client_id" not in opts


def test_import_options_contains_file_and_auth():
    opts = CommonOptions.import_options()

    assert "file" in opts
    assert "jwk_path" in opts
    assert "sa_id" in opts
    assert "base_url" in opts
    assert "am_base_url" in opts
    assert "project_name" in opts
    assert "client_id" not in opts


def test_export_options_contains_dir_file_and_auth():
    opts = CommonOptions.export_options()

    assert "output_dir" in opts
    assert "output_file" in opts
    assert "jwk_path" in opts
    assert "sa_id" in opts
    assert "base_url" in opts
    assert "am_base_url" in opts
    assert "project_name" in opts
    assert "client_id" not in opts


def test_create_auth_params_returns_five_params():
    params = create_auth_params()

    # jwk_path, sa_id, base_url, am_base_url, project_name
    assert len(params) == 5
    assert all(isinstance(p, typer.models.OptionInfo) for p in params)


def test_create_import_params_has_file_first():
    params = create_import_params()

    assert len(params) == 6
    assert isinstance(params[0], typer.models.OptionInfo)
    assert params[0].param_decls[0] == "--file"


def test_create_export_params_has_dir_and_file():
    params = create_export_params()

    flags = []
    for p in params:
        flags.extend(p.param_decls)

    assert "--dir" in flags
    assert "--file" in flags


def test_continue_on_error_option_uses_typer_boolean_flag():
    """Leaf import/export commands use this paired flag; default is stop-on-error."""
    opt = ContinueOnErrorOpt.__metadata__[0]
    assert isinstance(opt, typer.models.OptionInfo)
    decls = opt.param_decls
    assert any(
        isinstance(d, str) and "continue-on-error" in d and "stop-on-error" in d
        for d in decls
    )
