# Advanced Features

TRXO includes powerful safeguards and control mechanisms to ensure safe deployments.

## 🔍 Diff Preview (`--diff`)
**"Know before you go."**
The diff feature compares the configuration in your source (File/Git) against the target environment *before* making any changes.

**Usage:**
```bash
trxo import managed --file objects.json --diff
```
**Output:**
- Displays a summary of differences between server configuration and import file, including total items and counts of added, modified, and removed entries.
- Presents a tabular view of detailed changes, listing each item’s ID, name, change type (Added / Modified / Removed), and a short summary.
- Generates an HTML diff report with side-by-side, color-coded comparisons, highlighting exact field-level changes for each script or JSON configuration.

## 🍒 Cherry-Pick (`--cherry-pick`)
**"Deploy exactly what you need."**
Instead of overwriting everything, select specific items to import.

**Usage:**
```bash
# Import a single item
trxo import journeys --file alpha_journeys.json --cherry-pick LoginTree

# Import multiple items (comma-separated)
trxo import scripts --file alpha_scripts.json --cherry-pick script-id-1,script-id-2
```

## 🔄 Sync Mode (`--sync`)
**"Mirror source to target."**
By default, TRXO *updates* existing items and *adds* new ones. Sync mode ensures the target matches the source exactly by **deleting** items in the target that are missing from the source.

**Usage:**
```bash
trxo import services --file alpha_services.json --sync
```
*Use with caution! This will delete configurations in the target environment.*

## ⏪ Rollback (`--rollback`)
**"Safety net for deployments."**
Available in **Git Mode**. If you enable this flag, TRXO tracks the changes it makes during an import. If any error occurs midway, it automatically reverts the successful changes to restore the environment to its initial state.

**Usage:**
```bash
trxo import scripts --branch release --rollback
```

## 📦 Batch Operations
**"Bulk migration."**
Perform export or import operations for multiple configuration types (Scripts, Journeys, Services, etc.) in a single command.

See [Batch Operations Guide](BATCH_OPERATIONS.md) for details.
