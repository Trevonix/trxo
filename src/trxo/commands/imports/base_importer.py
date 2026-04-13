"""
Base importer class for import commands.

This module provides the base class for all import operations with
common functionality like file loading, API calls, and progress tracking.

Refactored to use focused utility modules for better maintainability.
"""

from abc import abstractmethod
from typing import Any, Dict, List, Optional

import typer

from trxo.constants import DEFAULT_REALM
from trxo.utils.console import error, info, success, warning
from trxo.utils.git import GitManager, setup_git_for_import
from trxo.utils.hash_manager import (
    HashManager,
    get_command_name_from_item_type,
)
from trxo.utils.imports.cherry_pick_filter import CherryPickFilter
from trxo.utils.imports.component_mapper import ComponentMapper
from trxo.utils.imports.file_loader import FileLoader
from trxo.utils.imports.sync_handler import SyncHandler

from ..shared.base_command import BaseCommand


class BaseImporter(BaseCommand):
    """Base class for all import operations"""

    def __init__(self):
        super().__init__()
        self.hash_manager = HashManager(self.config_store)
        self._git_manager = None
        self.component_mapper = ComponentMapper()
        self.file_loader = FileLoader()
        self.cherry_pick_filter = CherryPickFilter()
        self.sync_handler = SyncHandler()

    def import_from_file(
        self,
        file_path: Optional[str] = None,
        realm: Optional[str] = None,
        src_realm: Optional[str] = None,
        jwk_path: Optional[str] = None,
        sa_id: Optional[str] = None,
        base_url: Optional[str] = None,
        project_name: Optional[str] = None,
        auth_mode: Optional[str] = None,
        onprem_username: Optional[str] = None,
        onprem_password: Optional[str] = None,
        onprem_realm: Optional[str] = None,
        idm_base_url: Optional[str] = None,
        idm_username: Optional[str] = None,
        idm_password: Optional[str] = None,
        am_base_url: Optional[str] = None,
        force_import: bool = False,
        branch: Optional[str] = None,
        diff: bool = False,
        rollback: bool = False,
        continue_on_error: bool = False,
        sync: bool = False,
        cherry_pick: Optional[str] = None,
        dry_run: bool = False,
        **kwargs,
    ) -> None:
        """Main import workflow with Git and local storage support."""
        item_type = self.get_item_type()
        self.logger.info(f"Starting import operation: {item_type}")
        try:
            # Handle diff mode - show differences and exit (requires auth)
            if diff:
                token, api_base_url = self.initialize_auth(
                    jwk_path=jwk_path,
                    sa_id=sa_id,
                    base_url=base_url,
                    project_name=project_name,
                    auth_mode=auth_mode,
                    onprem_username=onprem_username,
                    onprem_password=onprem_password,
                    onprem_realm=onprem_realm,
                    idm_base_url=idm_base_url,
                    idm_username=idm_username,
                    idm_password=idm_password,
                    am_base_url=am_base_url,
                )
                self.logger.debug(
                    f"Authentication initialized for {item_type} import, "
                    f"auth_mode: {self.auth_mode}"
                )
                self._perform_diff_analysis(
                    file_path=file_path,
                    realm=realm,
                    jwk_path=jwk_path,
                    sa_id=sa_id,
                    base_url=base_url,
                    project_name=project_name,
                    auth_mode=auth_mode,
                    onprem_username=onprem_username,
                    onprem_password=onprem_password,
                    onprem_realm=onprem_realm,
                    idm_base_url=idm_base_url,
                    idm_username=idm_username,
                    idm_password=idm_password,
                    am_base_url=am_base_url,
                    branch=branch,
                    **kwargs,
                )
                return

            # Determine storage mode and load data (no PingOne auth for dry run)
            storage_mode = self._get_storage_mode()
            item_type = self.get_item_type()

            if storage_mode == "git":
                effective_src_realm = src_realm if src_realm is not None else realm
                items_to_process = self._import_from_git(
                    effective_src_realm, force_import, branch
                )
            else:
                if not file_path:
                    error("File path is required for local storage mode")
                    raise typer.Exit(1)
                items_to_process = self._import_from_local(file_path, force_import)

            if not items_to_process:
                warning("No items found to import")
                return

            # Apply cherry-pick filtering if specified
            if cherry_pick:
                items_to_process = self._apply_cherry_pick_filter(
                    items_to_process, cherry_pick
                )
                if not items_to_process:
                    return

            if dry_run:
                self._print_dry_run_plan(
                    items_to_process,
                    storage_mode=storage_mode,
                    file_path=file_path,
                    cherry_pick=cherry_pick,
                    sync=sync,
                    rollback=rollback,
                    continue_on_error=continue_on_error,
                    realm=realm,
                )
                return

            success(f"Loaded {len(items_to_process)} {item_type} for import")

            token, api_base_url = self.initialize_auth(
                jwk_path=jwk_path,
                sa_id=sa_id,
                base_url=base_url,
                project_name=project_name,
                auth_mode=auth_mode,
                onprem_username=onprem_username,
                onprem_password=onprem_password,
                onprem_realm=onprem_realm,
                idm_base_url=idm_base_url,
                idm_username=idm_username,
                idm_password=idm_password,
                am_base_url=am_base_url,
            )
            self.logger.debug(
                f"Authentication initialized for {item_type} import, "
                f"auth_mode: {self.auth_mode}"
            )

            # If rollback requested, create a baseline snapshot first
            rollback_manager = self._setup_rollback_manager(
                rollback, storage_mode, realm, branch, token, api_base_url
            )

            self.rollback_manager = rollback_manager

            # Process items (track for rollback if requested)
            self.process_items(
                items_to_process,
                token,
                api_base_url,
                rollback_manager=rollback_manager,
                rollback_on_failure=rollback,
                continue_on_error=continue_on_error,
            )

            # Handle sync deletions if sync mode enabled
            if sync:
                self._handle_sync_deletions(
                    token=token,
                    base_url=api_base_url,
                    file_path=file_path,
                    realm=realm,
                    jwk_path=jwk_path,
                    sa_id=sa_id,
                    project_name=project_name,
                    auth_mode=auth_mode,
                    onprem_username=onprem_username,
                    onprem_password=onprem_password,
                    onprem_realm=onprem_realm,
                    idm_base_url=idm_base_url,
                    idm_username=idm_username,
                    idm_password=idm_password,
                    am_base_url=am_base_url,
                    branch=branch,
                    force=True,  # User requested direct deletion without permission prompt
                    **kwargs,
                )

            # Print summary
            self.print_summary()

        finally:
            # Clean up resources
            self.cleanup()

    def process_items(
        self,
        items: List[Dict[str, Any]],
        token: str,
        base_url: str,
        rollback_manager: Optional[object] = None,
        rollback_on_failure: bool = False,
        continue_on_error: bool = False,
    ) -> None:
        """Process all items and track success/failure"""
        item_type = self.get_item_type()
        info(f"Processing {len(items)} {item_type}...")

        items = [item for item in items if isinstance(item, dict)]

        self.successful_updates = 0
        self.failed_updates = 0
        self.continue_on_error = continue_on_error

        for item in items:
            item_id = self._get_item_identifier(item)

            baseline_item = None
            action = "created"

            if (
                rollback_manager
                and item_id
                and str(item_id) in rollback_manager.baseline_snapshot
            ):
                baseline_item = rollback_manager.baseline_snapshot.get(str(item_id))
                action = "updated"

            try:
                if self.update_item(item, token, base_url):
                    self.successful_updates += 1

                    # Use entityId for SAML items if present
                    track_id = self._get_item_identifier(item)

                    if rollback_manager and track_id:
                        rollback_manager.track_import(
                            str(track_id), action, baseline_item
                        )
                else:
                    self.failed_updates += 1

                    if rollback_on_failure and rollback_manager:
                        self._execute_rollback_and_exit(
                            rollback_manager, token, base_url, item_id
                        )
                    if not continue_on_error:
                        error(
                            f"Stopping import due to failed item: {item_id or '<unknown>'}"
                        )
                        raise typer.Exit(1)

            except typer.Exit:
                raise

            except Exception as e:
                self.failed_updates += 1

                if rollback_on_failure and rollback_manager:
                    info(
                        f"Import failed on item {item_id or '<unknown>'} - executing rollback"
                    )

                    report = rollback_manager.execute_rollback(token, base_url)
                    self._print_rollback_report(report)

                    raise typer.Exit(1)
                if not continue_on_error:
                    error(
                        f"Stopping import due to error on item: {item_id or '<unknown>'}"
                    )
                    raise typer.Exit(1)

    def _print_dry_run_plan(
        self,
        items: List[Dict[str, Any]],
        *,
        storage_mode: str,
        file_path: Optional[str],
        cherry_pick: Optional[str],
        sync: bool,
        rollback: bool,
        continue_on_error: bool,
        realm: Optional[str],
    ) -> None:
        """Medium-detail dry run: explain what a real import would do."""
        item_type = self.get_item_type()
        n = sum(1 for i in items if isinstance(i, dict))

        info("Dry run — no API calls. A real run would:")
        if storage_mode == "git":
            info(
                "  • Use export data already loaded from Git for this component "
                "(branch/realm per project settings)."
            )
        else:
            src = file_path or "(unspecified file)"
            info(f"  • Read items from the local JSON file (your --file path): {src}")

        if realm is not None:
            info(f"  • Target realm context: {realm}")

        info("  • Authenticate (service account / configured auth mode).")
        info(
            f"  • Send API requests to create or update {n} {item_type} item(s) "
            "(upsert each record)."
        )

        if cherry_pick:
            info(f"  • Honor --cherry-pick (only these IDs): {cherry_pick}")

        if rollback:
            info(
                "  • With --rollback: save a baseline snapshot first, then roll "
                "back if an item fails (where supported)."
            )
        if sync:
            info(
                "  • With --sync: remove server-side items that are not in this "
                "export."
            )
        if continue_on_error:
            info("  • With --continue-on-error: keep going after individual failures.")
        else:
            info("  • Stop on the first failed item (unless --continue-on-error).")

        ids: List[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            ident = self._get_item_identifier(item)
            if ident is not None:
                ids.append(str(ident))
        if ids:
            cap = 8
            head = ids[:cap]
            preview = ", ".join(head)
            rest = len(ids) - cap
            if rest > 0:
                info(f"  • IDs in scope (sample): {preview} … (+{rest} more)")
            else:
                info(f"  • IDs in scope: {preview}")

    # ==================== Private Helper Methods ====================

    def _get_storage_mode(self) -> str:
        """Get storage mode from project configuration"""
        try:
            current_project = self.config_store.get_current_project()
            if current_project:
                project_config = self.config_store.get_project_config(current_project)
                return project_config.get("storage_mode", "local")
            return "local"
        except Exception:
            return "local"

    def _setup_git_manager(self, branch: str = None) -> GitManager:
        """Setup Git manager for Git operations"""
        if self._git_manager is None:
            try:
                current_project = self.config_store.get_current_project()
                git_credentials = self.config_store.get_git_credentials(current_project)
                if not git_credentials or not all(git_credentials.values()):
                    error(
                        "Git credentials not found. Please run 'trxo config' "
                        "to set up Git integration."
                    )
                    raise typer.Exit(1)

                username, repo_url, token = git_credentials.values()
                self._git_manager = setup_git_for_import(
                    username, token, repo_url, branch
                )
            except Exception as e:
                error(f"Failed to setup Git manager: {e}")
                raise typer.Exit(1)
        return self._git_manager

    def _import_from_local(
        self, file_path: str, force_import: bool
    ) -> List[Dict[str, Any]]:
        """Import from local file with hash validation"""
        item_type = self.get_item_type()
        info(f"Loading {item_type} from local file: {file_path}")

        try:
            # Read raw file content first so hash validation can use
            # the original exported structure (avoids normalization differences)
            import json
            import os

            if not os.path.isabs(file_path):
                file_path_abs = os.path.abspath(file_path)
            else:
                file_path_abs = file_path

            with open(file_path_abs, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            # Normalize items for processing. Prefer importer-specific loader
            # if it exists (some importers provide custom normalization).
            if hasattr(self, "load_data_from_file"):
                items_to_process = self.load_data_from_file(file_path)
            else:
                items_to_process = self.file_loader.load_from_local_file(file_path)

            # Validate required fields on normalized items
            self._validate_items(items_to_process)

            # Validate import hash against raw file content so the hash
            # matches whatever was generated at export time (wrapper vs list)
            if not self.validate_import_hash(raw_data, force_import):
                error("Import validation failed: Hash mismatch with exported data")
                raise typer.Exit(1)

            return items_to_process
        except Exception as e:
            error(f"Failed to load {item_type} from local file: {str(e)}")
            raise typer.Exit(1)

    def _import_from_git(
        self, realm: Optional[str], force_import: bool, branch: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Import from Git repository with intelligent file discovery"""
        item_type = self.get_item_type()

        # Determine effective realm based on component type
        effective_realm = self._determine_effective_realm(realm, item_type, branch)

        # Setup Git manager with optional branch
        git_manager = self._setup_git_manager(branch)

        # Load files from Git
        all_items = self.file_loader.load_git_files(
            git_manager, item_type, effective_realm, branch
        )

        if not all_items:
            self._handle_no_git_files_found(item_type, effective_realm, realm)
            return []

        # Normalize Git export format
        # Prefer importer-specific normalization if it exists
        if hasattr(self, "load_data_from_items"):
            return self.load_data_from_items(all_items)

        # Default normalization
        normalized_items = []
        for item in all_items:
            if not isinstance(item, dict):
                continue

            if self._get_item_identifier(item) is None:
                continue

            normalized_items.append(item)

        if not normalized_items:
            self._handle_no_git_files_found(item_type, effective_realm, realm)
            return []

        return normalized_items

    def _determine_effective_realm(
        self,
        realm: Optional[str],
        item_type: str,
        branch: Optional[str],
    ) -> Optional[str]:
        """Determine effective realm based on component type"""
        if self.component_mapper.is_root_level_component(item_type):
            # Root-level configs always use 'root' realm
            if branch:
                info(
                    f"Loading {item_type} from Git repository "
                    f"(root level, branch: {branch})..."
                )
            else:
                info(f"Loading {item_type} from Git repository...")
            return "root"
        else:
            # Realm-specific configs default to DEFAULT_REALM
            effective_realm = realm if realm is not None else DEFAULT_REALM
            if branch:
                info(
                    f"Loading {item_type} from Git repository "
                    f"(realm: {effective_realm}, branch: {branch})..."
                )
            else:
                info(
                    f"Loading {item_type} from Git repository "
                    f"(realm: {effective_realm})..."
                )
            return effective_realm

    def _handle_no_git_files_found(
        self,
        item_type: str,
        effective_realm: Optional[str],
        realm: Optional[str],
    ):
        """Handle case when no Git files are found"""
        if self.component_mapper.is_root_level_component(item_type):
            error(f"No {item_type} files found in Git repository (root level)")
        else:
            error(
                f"No {item_type} files found for realm '{effective_realm}' "
                "in Git repository"
            )
            if realm is None:
                error(
                    f"Defaulted to '{DEFAULT_REALM}' realm. Use --realm to "
                    "specify a different realm"
                )

    def _validate_items(self, items: List[Dict[str, Any]]):
        """Validate each item has required fields"""
        required_fields = self.get_required_fields()
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"Invalid item at index {i}: Should be an object")

            for field in required_fields:
                if field not in item:
                    raise ValueError(
                        f"Invalid item at index {i}: Missing required field '{field}'"
                    )

    def _apply_cherry_pick_filter(
        self, items: List[Dict[str, Any]], cherry_pick: str
    ) -> List[Dict[str, Any]]:
        """Apply cherry-pick filtering to items"""
        # Validate cherry-pick argument
        if not self.cherry_pick_filter.validate_cherry_pick_argument(cherry_pick):
            error(
                f"Invalid cherry-pick ID: '{cherry_pick}'. "
                "Please provide a valid item ID."
            )
            error("Usage: --cherry-pick <id1> or --cherry-pick <id1,id2,id3>")
            raise typer.Exit(1)

        filtered_items = self.cherry_pick_filter.apply_filter(items, cherry_pick)

        if not filtered_items:
            # Parse IDs for better error message
            cherry_pick_ids = [
                id.strip() for id in cherry_pick.split(",") if id.strip()
            ]
            if len(cherry_pick_ids) == 1:
                warning(
                    f"No items found with ID '{cherry_pick_ids[0]}' "
                    "for cherry-pick import"
                )
            else:
                warning(
                    f"No items found with IDs {cherry_pick_ids} "
                    "for cherry-pick import"
                )

        return filtered_items

    def _setup_rollback_manager(
        self,
        rollback: bool,
        storage_mode: str,
        realm: Optional[str],
        branch: Optional[str],
        token: str,
        api_base_url: str,
    ) -> Optional[object]:
        """Setup rollback manager if requested"""
        if not rollback:
            return None

        try:
            from trxo.utils.hash_manager import get_command_name_from_item_type
            from trxo.utils.rollback_manager import RollbackManager

            command_name = get_command_name_from_item_type(self.get_item_type())
            project_name = self.config_store.get_current_project()
            rollback_manager = RollbackManager(
                command_name, realm, project_name=project_name
            )

            # Provide GitManager if in git mode so snapshot is persisted
            git_mgr = None
            if storage_mode == "git":
                git_mgr = self._setup_git_manager(branch)

            created = rollback_manager.create_baseline_snapshot(
                token,
                api_base_url,
                git_manager=git_mgr,
                auth_mode=self.auth_mode,
                idm_username=self._idm_username,
                idm_password=self._idm_password,
                idm_base_url=self._idm_base_url,
            )

            if not created:
                warning(
                    "Could not create baseline snapshot - "
                    "rollback will be unavailable if import fails"
                )

            return rollback_manager
        except Exception as e:
            warning(f"Failed to initialize rollback manager: {e}")
            return None

    def _execute_rollback_and_exit(
        self,
        rollback_manager: object,
        token: str,
        base_url: str,
        item_id: Optional[str],
    ):
        """Execute rollback and exit"""
        info(
            f"\nImport failed on item {item_id or '<unknown>'} - " "executing rollback"
        )
        report = rollback_manager.execute_rollback(token, base_url)
        self._print_rollback_report(report)
        raise typer.Exit(1)

    def _get_item_identifier(self, item: Dict[str, Any]) -> Optional[str]:
        if not isinstance(item, dict):
            return None

        # Allow importer to define its own identifier
        if hasattr(self, "get_item_id"):
            custom_id = self.get_item_id(item)
            if custom_id:
                return custom_id

        if item.get("_id"):
            return item.get("_id")

        type_info = item.get("_type", {})
        type_id = type_info.get("_id")

        if type_id:
            return type_id

        return item.get("id") or item.get("name")

    def _perform_diff_analysis(
        self,
        file_path: Optional[str] = None,
        realm: Optional[str] = None,
        jwk_path: Optional[str] = None,
        sa_id: Optional[str] = None,
        base_url: Optional[str] = None,
        project_name: Optional[str] = None,
        auth_mode: Optional[str] = None,
        onprem_username: Optional[str] = None,
        onprem_password: Optional[str] = None,
        onprem_realm: Optional[str] = None,
        idm_base_url: Optional[str] = None,
        idm_username: Optional[str] = None,
        idm_password: Optional[str] = None,
        am_base_url: Optional[str] = None,
        branch: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Perform diff analysis and display results"""
        try:
            from trxo.utils.diff.diff_manager import DiffManager

            # Get command name for data fetcher
            command_name = self.component_mapper.get_command_name(self.get_item_type())

            # Create diff manager and perform analysis
            diff_manager = DiffManager()
            diff_result = diff_manager.perform_diff(
                command_name=command_name,
                file_path=file_path,
                realm=realm,
                jwk_path=jwk_path,
                sa_id=sa_id,
                base_url=base_url,
                project_name=project_name,
                auth_mode=auth_mode,
                onprem_username=onprem_username,
                onprem_password=onprem_password,
                onprem_realm=onprem_realm,
                idm_base_url=idm_base_url,
                idm_username=idm_username,
                idm_password=idm_password,
                am_base_url=am_base_url,
                branch=branch,
                generate_html=True,
                global_policy=getattr(self, "global_policy", False),
            )

            if diff_result:
                # Show summary of what would happen
                total_changes = (
                    len(diff_result.added_items)
                    + len(diff_result.modified_items)
                    + len(diff_result.removed_items)
                )

                if total_changes > 0:
                    warning(f"Import would make {total_changes} changes")
                    info(
                        "Use the import command without --diff to proceed "
                        "with the import"
                    )
                else:
                    success("No changes would be made - data is already up to date")
            else:
                error("Diff analysis failed")

        except ImportError:
            error(
                "Diff functionality requires deepdiff. "
                "Install with: pip install deepdiff>=6.0.0"
            )
        except Exception as e:
            error(f"Diff analysis failed: {str(e)}")

    def _print_rollback_report(self, report: Dict[str, Any]) -> None:
        """Print a formatted rollback report"""
        # Print rolled back items
        rolled_back = report.get("rolled_back", [])
        if len(rolled_back) >= 1:
            print("\n" + "=" * 60)
            print("\t\t\tROLLBACK REPORT")
            print("=" * 60)
            info(f"✓ Successfully rolled back {len(rolled_back)} item(s):")
            for item in rolled_back:
                if "action" in item and "id" not in item:
                    # Managed config restore
                    info(f"  • {item['action']}")
                else:
                    item_id = item.get("id", "unknown")
                    action = item.get("action", "unknown")
                    info(f"  • {item_id} ({action})")
        else:
            print("\nNo Items were rolled back, as the first item was failed.")

        # Print errors
        errors = report.get("errors", [])
        if errors:
            warning(f"✗ Failed to roll back {len(errors)} item(s):")
            for error_item in errors:
                item_id = error_item.get("id", "unknown")
                error_msg = error_item.get("error", "unknown error")
                warning(f"  • {item_id}: {error_msg}")

        print("=" * 60 + "\n")

    def _handle_sync_deletions(
        self,
        token: str,
        base_url: str,
        file_path: Optional[str] = None,
        realm: Optional[str] = None,
        jwk_path: Optional[str] = None,
        sa_id: Optional[str] = None,
        project_name: Optional[str] = None,
        auth_mode: Optional[str] = None,
        onprem_username: Optional[str] = None,
        onprem_password: Optional[str] = None,
        onprem_realm: Optional[str] = None,
        idm_base_url: Optional[str] = None,
        idm_username: Optional[str] = None,
        idm_password: Optional[str] = None,
        am_base_url: Optional[str] = None,
        branch: Optional[str] = None,
        force: bool = False,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """Handle deletion of orphaned items in sync mode"""
        command_name = self.component_mapper.get_command_name(self.get_item_type())

        return self.sync_handler.handle_sync_deletions(
            command_name=command_name,
            item_type=self.get_item_type(),
            delete_func=self.delete_item,
            token=token,
            base_url=base_url,
            file_path=file_path,
            realm=realm,
            jwk_path=jwk_path,
            sa_id=sa_id,
            project_name=project_name,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
            idm_base_url=idm_base_url,
            idm_username=idm_username,
            idm_password=idm_password,
            am_base_url=am_base_url,
            branch=branch,
            force=force,
            **kwargs,
        )

    # ==================== Validation Methods ====================

    def validate_import_hash(
        self, items_to_process: List[Dict[str, Any]], force: bool = False
    ) -> bool:
        """Validate import data hash against stored export hash"""
        # Get command name for hash lookup
        command_name = get_command_name_from_item_type(self.get_item_type())

        # Use HashManager for validation
        return self.hash_manager.validate_import_hash(
            items_to_process, command_name, force
        )

    # ==================== Abstract Methods ====================

    @abstractmethod
    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        """Return the API endpoint for updating an item"""
        pass

    @abstractmethod
    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        """Update a single item via API"""
        pass

    def delete_item(self, item_id: str, token: str, base_url: str) -> bool:
        """
        Delete a single item via API.

        Default implementation - should be overridden by importers that support sync.

        Args:
            item_id: ID of item to delete
            token: Authentication token
            base_url: API base URL

        Returns:
            True if deletion successful, False otherwise
        """
        pass


class SimpleImporter(BaseImporter):
    """Simple importer for basic operations (like argument mode support)"""

    def get_required_fields(self) -> List[str]:
        return []

    def get_item_type(self) -> str:
        return "items"

    def get_api_endpoint(self, item_id: str, base_url: str) -> str:
        return f"{base_url}/dummy"

    def update_item(self, item_data: Dict[str, Any], token: str, base_url: str) -> bool:
        return True

    def delete_item(self, item_id: str, token: str, base_url: str) -> bool:
        return True
