import typer
from typing import Optional
from trxo.utils.config_store import ConfigStore
from trxo.utils.console import console, success, error, info, create_table

app = typer.Typer(help="Manage projects")
config_store = ConfigStore()


@app.command("create")
def create_project(
    name: str = typer.Argument(..., help="Project name"),
    description: Optional[str] = typer.Option(None, help="Project description"),
):
    """Create a new project"""
    projects = config_store.get_projects()

    if name in projects:
        error(f"Project '{name}' already exists")
        raise typer.Exit(1)

    project_config = {
        "description": description or f"PingOne Advanced Identity Cloud project: {name}"
    }

    config_store.save_project(name, project_config)
    success(f"Project '{name}' created successfully!")
    console.print()  # Empty line for spacing
    info("📋 Next steps:")
    info(f"   1. Switch to your project: trxo project switch {name}")
    info("   2. Configure authentication: trxo config setup")
    info("   3. Start using export/import commands")
    console.print()  # Empty line for spacing
    info(
        "💡 Tip: You can also use argument mode by providing all credentials as arguments"
    )


@app.command()
def switch(project_name: str = typer.Argument(..., help="Project name to switch to")):
    """Switch to a project"""
    projects = config_store.get_projects()

    if project_name not in projects:
        error(f"Project '{project_name}' not found")
        raise typer.Exit(1)

    config_store.set_current_project(project_name)
    success(f"Switched to project '{project_name}'")


def list_projects():
    """List all projects"""
    projects = config_store.get_projects()
    current_project = config_store.get_current_project()

    if not projects:
        info("No projects found. Create one with 'trxo project create <name>'")
        return

    table = create_table("Projects", ["Name", "Description", "Status", "Created"])

    for name, project in projects.items():
        status = "🟢 Active" if name == current_project else "⚪ Inactive"
        created = project.get("created_at", "Unknown")[:10]  # Just date part
        description = project.get("description", "No description")

        table.add_row(name, description, status, created)

    console.print(table)


@app.command("delete")
def delete_project(project_name: str):
    """Delete a project"""
    projects = config_store.get_projects()

    if project_name not in projects:
        error(f"Project '{project_name}' not found")
        raise typer.Exit(1)

    config_store.delete_project(project_name)
    success(f"Project '{project_name}' deleted successfully")
