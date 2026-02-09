import pytest
import typer

from trxo.commands.project import (
    create_project,
    switch,
    list_projects,
    delete_project,
)


def test_create_project_success(mocker):
    mock_store = mocker.patch("trxo.commands.project.config_store")
    mock_store.get_projects.return_value = {}

    create_project(name="proj1", description="desc")

    mock_store.save_project.assert_called_once()
    mock_store.get_projects.assert_called_once()


def test_create_project_already_exists(mocker):
    mock_store = mocker.patch("trxo.commands.project.config_store")
    mock_store.get_projects.return_value = {"proj1": {}}

    with pytest.raises(typer.Exit):
        create_project(name="proj1", description=None)


def test_switch_project_success(mocker):
    mock_store = mocker.patch("trxo.commands.project.config_store")
    mock_store.get_projects.return_value = {"proj1": {}}

    switch(project_name="proj1")

    mock_store.set_current_project.assert_called_once_with("proj1")


def test_switch_project_not_found(mocker):
    mock_store = mocker.patch("trxo.commands.project.config_store")
    mock_store.get_projects.return_value = {}

    with pytest.raises(typer.Exit):
        switch(project_name="missing")


def test_list_projects_no_projects(mocker):
    mock_store = mocker.patch("trxo.commands.project.config_store")
    mock_store.get_projects.return_value = {}
    mock_store.get_current_project.return_value = None

    list_projects()

    mock_store.get_projects.assert_called_once()


def test_list_projects_with_projects(mocker):
    mock_store = mocker.patch("trxo.commands.project.config_store")
    mock_store.get_projects.return_value = {
        "proj1": {"description": "d1", "created_at": "2025-01-01T10:00:00"},
        "proj2": {"description": "d2", "created_at": "2025-01-02T10:00:00"},
    }
    mock_store.get_current_project.return_value = "proj1"

    mock_table = mocker.Mock()
    mocker.patch("trxo.commands.project.create_table", return_value=mock_table)

    list_projects()

    assert mock_table.add_row.call_count == 2


def test_delete_project_success(mocker):
    mock_store = mocker.patch("trxo.commands.project.config_store")
    mock_store.get_projects.return_value = {"proj1": {}}

    delete_project("proj1")

    mock_store.delete_project.assert_called_once_with("proj1")


def test_delete_project_not_found(mocker):
    mock_store = mocker.patch("trxo.commands.project.config_store")
    mock_store.get_projects.return_value = {}

    with pytest.raises(typer.Exit):
        delete_project("missing")
