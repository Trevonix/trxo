"""
Base importer class for import commands.

This module provides the base class for all import operations with
common functionality like file loading, API calls, and progress tracking.

Refactored to use focused utility modules for better maintainability.
"""

import typer
from typing import Optional, List, Dict, Any
from abc import abstractmethod
from trxo.utils.console import success, error, info, warning
from trxo.utils.hash_manager import (
    HashManager,
    get_command_name_from_item_type,
)
from trxo.utils.git import setup_git_for_import, GitManager
from ..shared.base_command import BaseCommand
from trxo.utils.imports.component_mapper import ComponentMapper
from trxo.utils.imports.file_loader import FileLoader
from trxo.utils.imports.cherry_pick_filter import CherryPickFilter
from trxo.utils.imports.sync_handler import SyncHandler
from trxo.constants import DEFAULT_REALM


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
        jwk_path: Optional[str] = None,
        client_id: Optional[str] = None,
        sa_id: Optional[str] = None,
        base_url: Optional[str] = None,
        project_name: Optional[str] = None,
        auth_mode: Optional[str] = None,
        onprem_username: Optional[str] = None,
        onprem_password: Optional[str] = None,
        onprem_realm: Optional[str] = None,
        force_import: bool = False,
        branch: Optional[str] = None,
        diff: bool = False,
        rollback: bool = False,
        sync: bool = False,
        cherry_pick: Optional[str] = None,
    ) -> None:
        """Main import workflow with Git and local storage support."""
        item_type = self.get_item_type()
        self.logger.info(f"Starting import operation: {item_type}")
        try:
            # Initialize authentication
            token, api_base_url = self.initialize_auth(
                jwk_path=jwk_path,
                client_id=client_id,
                sa_id=sa_id,
                base_url=base_url,
                project_name=project_name,
                auth_mode=auth_mode,
                onprem_username=onprem_username,
                onprem_password=onprem_password,
                onprem_realm=onprem_realm,
            )
            self.logger.debug(
                f"Authentication initialized for {item_type} import, "
                f"auth_mode: {self.auth_mode}"
            )

            # Handle diff mode - show differences and exit
            if diff:
                self._perform_diff_analysis(
                    file_path=file_path,
                    realm=realm,
                    jwk_path=jwk_path,
                    client_id=client_id,
                    sa_id=sa_id,
                    base_url=base_url,
                    project_name=project_name,
                    auth_mode=auth_mode,
                    onprem_username=onprem_username,
                    onprem_password=onprem_password,
                    onprem_realm=onprem_realm,
                    branch=branch,
                )
                return

            # Determine storage mode and load data
            storage_mode = self._get_storage_mode()
            item_type = self.get_item_type()

            if storage_mode == "git":
                items_to_process = self._import_from_git(realm, force_import, branch)
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

            success(f"Loaded {len(items_to_process)} {item_type} for import")

            # If rollback requested, create a baseline snapshot first
            rollback_manager = self._setup_rollback_manager(
                rollback, storage_mode, realm, branch, token, api_base_url
            )

            # Process items (track for rollback if requested)
            self.process_items(
                items_to_process,
                token,
                api_base_url,
                rollback_manager=rollback_manager,
                rollback_on_failure=rollback,
            )

            # Handle sync deletions if sync mode enabled
            if sync:
                self._handle_sync_deletions(
                    token=token,
                    base_url=api_base_url,
                    file_path=file_path,
                    realm=realm,
                    jwk_path=jwk_path,
                    client_id=client_id,
                    sa_id=sa_id,
                    project_name=project_name,
                    auth_mode=auth_mode,
                    onprem_username=onprem_username,
                    onprem_password=onprem_password,
                    onprem_realm=onprem_realm,
                    branch=branch,
                    force=force_import,
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
    ) -> None:
        """Process all items and track success/failure"""
        item_type = self.get_item_type()
        info(f"Processing {len(items)} {item_type}...")

        self.successful_updates = 0
        self.failed_updates = 0

        for item in items:
            # Determine item identifier
            item_id = self._get_item_identifier(item)

            action = "updated"
            baseline_item = None
            if rollback_manager and item_id:
                baseline_item = rollback_manager.baseline_snapshot.get(str(item_id))
                action = "updated" if baseline_item else "created"

            try:
                if self.update_item(item, token, base_url):
                    self.successful_updates += 1
                    # Track for rollback
                    if rollback_manager and item_id:
                        rollback_manager.track_import(
                            str(item_id), action, baseline_item
                        )
                else:
                    self.failed_updates += 1
                    # On failure, if rollback requested, execute rollback ONCE and exit
                    if rollback_on_failure and rollback_manager:
                        self._execute_rollback_and_exit(
                            rollback_manager, token, base_url, item_id
                        )
            except typer.Exit:
                # Re-raise Exit exceptions without catching them
                raise
            except Exception as e:
                self.failed_updates += 1
                if rollback_on_failure and rollback_manager:
                    info(
                        f"Exception during import of "
                        f"{item_id or '<unknown>'}: {e} - executing rollback"
                    )
                    report = rollback_manager.execute_rollback(token, base_url)
                    self._print_rollback_report(report)
                    raise typer.Exit(1)

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
            items_to_process = self.file_loader.load_from_local_file(file_path)

            # Validate required fields
            self._validate_items(items_to_process)

            # Generate hash for import data and validate against stored export hash
            if not self.validate_import_hash(items_to_process, force_import):
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

        return all_items

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
            from trxo.utils.rollback_manager import RollbackManager

            rollback_manager = RollbackManager(self.get_item_type(), realm)

            # Provide GitManager if in git mode so snapshot is persisted
            git_mgr = None
            if storage_mode == "git":
                git_mgr = self._setup_git_manager(branch)

            created = rollback_manager.create_baseline_snapshot(
                token, api_base_url, git_mgr
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
        """Get item identifier from item data"""
        if isinstance(item, dict):
            return item.get("_id") or item.get("id") or item.get("name")
        return None

    def _perform_diff_analysis(
        self,
        file_path: Optional[str] = None,
        realm: Optional[str] = None,
        jwk_path: Optional[str] = None,
        client_id: Optional[str] = None,
        sa_id: Optional[str] = None,
        base_url: Optional[str] = None,
        project_name: Optional[str] = None,
        auth_mode: Optional[str] = None,
        onprem_username: Optional[str] = None,
        onprem_password: Optional[str] = None,
        onprem_realm: Optional[str] = None,
        branch: Optional[str] = None,
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
                client_id=client_id,
                sa_id=sa_id,
                base_url=base_url,
                project_name=project_name,
                auth_mode=auth_mode,
                onprem_username=onprem_username,
                onprem_password=onprem_password,
                onprem_realm=onprem_realm,
                branch=branch,
                generate_html=True,
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
        client_id: Optional[str] = None,
        sa_id: Optional[str] = None,
        project_name: Optional[str] = None,
        auth_mode: Optional[str] = None,
        onprem_username: Optional[str] = None,
        onprem_password: Optional[str] = None,
        onprem_realm: Optional[str] = None,
        branch: Optional[str] = None,
        force: bool = False,
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
            client_id=client_id,
            sa_id=sa_id,
            project_name=project_name,
            auth_mode=auth_mode,
            onprem_username=onprem_username,
            onprem_password=onprem_password,
            onprem_realm=onprem_realm,
            branch=branch,
            force=force,
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
