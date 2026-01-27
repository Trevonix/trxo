# TRXO Batch Operations Guide

## Overview

TRXO supports batch operations to export and import multiple configurations in a single command. This is essential for full environment migrations or backups.

## Batch Export

### Basic Usage

```bash
# Export multiple configurations to a directory
trxo batch export realms services themes --dir batch_exports

# Export all available configurations
trxo batch export realms services themes scripts saml journeys oauth users agents authn email_templates endpoints policies managed mappings connectors
```

### Advanced Options

```bash
# Continue on errors (default)
trxo batch export realms services themes --continue-on-error

# Stop on first error (Critical constraints)
trxo batch export realms services themes --stop-on-error
```

## Batch Import

Batch import works by defining a configuration plan (Manifest) to ensure dependencies and order are respected.

### Step 1: Generate Configuration Template

```bash
# Generate import config template
trxo batch generate-config --type import --output my_imports.json
```

### Step 2: Edit Configuration File

Edit `my_imports.json` to define what to import:

```json
{
  "description": "Migration Plan",
  "imports": [
    {
      "command": "scripts",
      "file": "scripts_export.json"
    },
    {
      "command": "journeys",
      "file": "journeys_export.json"
    }
  ]
}
```

### Step 3: Run Batch Import

```bash
# Import using config file
trxo batch import my_imports.json

# Dry run (Preview)
trxo batch import my_imports.json --dry-run
```

## Best Practices

1.  **Use Configuration Files**: For complex migrations, define your plan in a JSON file rather than long CLI arguments.
2.  **Test with Dry Run**: Always validate the plan before execution.
3.  **Handle Errors**: Use `--stop-on-error` for critical production deployments where partial success is not acceptable.
