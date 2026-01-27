# Storage Modes: Local vs Git

TRXO offers two storage modes to suit your workflow: **Local Filesystem** and **Git Repository**.

## 📂 Local Mode (Default)
Ideal for ad-hoc backups or quick transfers between environments.

**How it works:**
- Exports are saved as JSON files in a local `./exports/` directory (or custom path).
- Imports read directly from these JSON files.

**Usage:**
```bash
# Export to local file
trxo export scripts

# Import from local file
trxo import scripts --file ./exports/scripts_timestamp.json
```

## 🐙 Git Mode
Ideal for team collaboration, version history, audit logs, and automated deployments.

**How it works:**
- TRXO connects directly to a remote Git repository (GitHub, GitLab, etc.).
- Exports create a commit on a specified branch.
- Imports read configurations directly from the repository structure.

### Setup
1. **Prepare a Repository**: Create an empty repo (e.g., `ping-configs`) on your Git provider.
2. **Configure TRXO**:
   ```bash
   trxo config setup
   # When prompted for storage, select 'git' (or configure git settings manually)
   # Provide: Git Username, Personal Access Token (PAT), and Repository URL
   ```

### Usage
```bash
# Export to 'develop' branch
trxo export scripts --branch develop --message "Updated authentication scripts"

# Import from 'main' branch
trxo import scripts --branch main
```

### Benefits of Git Mode
- **Rollback Support**: Use `--rollback` to automatically revert changes if an import fails.
- **Audit Trail**: Every change is a commit with a timestamp and author.
- **Structure**: Configurations are organized by Realm and Component type automatically (e.g., `alpha/scripts/my-script.json`).
