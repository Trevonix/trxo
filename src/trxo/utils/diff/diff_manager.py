"""
Main diff manager for import commands.

This module provides the main interface for diff functionality,
coordinating data fetching, comparison, and reporting.
"""

from typing import Dict, Any, Optional
from pathlib import Path
from trxo.utils.console import info, error
from trxo.utils.diff.data_fetcher import DataFetcher, get_command_api_endpoint
from trxo.utils.diff.diff_engine import DiffEngine, DiffResult
from trxo.utils.diff.diff_reporter import DiffReporter
from trxo.constants import DEFAULT_REALM


class DiffManager:
    """Main manager for diff functionality"""

    def __init__(self):
        self.data_fetcher = DataFetcher()
        self.diff_engine = DiffEngine()
        self.diff_reporter = DiffReporter()

    def perform_diff(
        self,
        command_name: str,
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
        generate_html: bool = True,
        html_output_dir: Optional[str] = None,
    ) -> Optional[DiffResult]:
        """
        Perform complete diff analysis

        Args:
            command_name: Name of the command (e.g., 'journeys', 'scripts')
            file_path: Path to import file (local mode)
            realm: Target realm
            jwk_path: Path to JWK file
            client_id: Client ID
            sa_id: Service account ID
            base_url: Base URL
            project_name: Project name
            auth_mode: Authentication mode
            onprem_username: On-premise username
            onprem_password: On-premise password
            onprem_realm: On-premise realm
            branch: Git branch
            generate_html: Whether to generate HTML report
            html_output_dir: Output directory for HTML report

        Returns:
            DiffResult or None if failed
        """
        try:
            info(f"Performing diff analysis for {command_name}...")

            # Step 1: Fetch current server data
            current_data = self._fetch_current_data(
                command_name=command_name,
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

            if not current_data:
                error("Failed to fetch current server data")
                return None

            # Step 2: Fetch new data to be imported
            info("Fetching import data (file or git)")
            new_data = self._fetch_import_data(
                command_name=command_name,
                file_path=file_path,
                branch=branch,
                project_name=project_name,
                realm=realm,
            )

            if not new_data:
                error("Failed to fetch import data")
                return None

            # Step 3: Perform comparison
            diff_result = self.diff_engine.compare_data(
                current_data=current_data,
                new_data=new_data,
                command_name=command_name,
                realm=realm,
            )

            # Step 4: Display summary
            self.diff_reporter.display_summary(diff_result)

            # Step 5: Generate HTML report if requested
            if generate_html:
                html_path = self.diff_reporter.generate_html_diff(
                    diff_result=diff_result,
                    current_data=current_data,
                    new_data=new_data,
                    output_dir=html_output_dir,
                )

                if html_path:
                    html_uri = Path(html_path).absolute().as_uri()
                    msg = f"Open HTML report: [link={html_uri}]{html_uri}[/link]"
                    info(msg)

            return diff_result

        except Exception as e:
            error(f"Diff analysis failed: {str(e)}")
            return None

    def _fetch_current_data(
        self,
        command_name: str,
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
    ) -> Optional[Dict[str, Any]]:
        """Fetch current data from server"""

        # Get API endpoint and response filter for the command
        api_endpoint, response_filter = get_command_api_endpoint(
            command_name, realm or DEFAULT_REALM
        )

        if not api_endpoint:
            error(f"Unknown command: {command_name}")
            return None

        return self.data_fetcher.fetch_data(
            command_name=command_name,
            api_endpoint=api_endpoint,
            response_filter=response_filter,
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

    def _fetch_import_data(
        self,
        command_name: str,
        file_path: Optional[str] = None,
        branch: Optional[str] = None,
        project_name: Optional[str] = None,
        realm: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch data to be imported"""
        return self.data_fetcher.fetch_from_file_or_git(
            command_name=command_name,
            file_path=file_path,
            branch=branch,
            project_name=project_name,
            realm=realm,
        )

    def quick_diff(
        self,
        command_name: str,
        current_data: Dict[str, Any],
        new_data: Dict[str, Any],
        realm: Optional[str] = None,
    ) -> Optional[DiffResult]:
        """
        Perform a quick diff with pre-loaded data

        Args:
            command_name: Name of the command
            current_data: Current server data
            new_data: New data to import
            realm: Target realm

        Returns:
            DiffResult or None if failed
        """
        try:
            diff_result = self.diff_engine.compare_data(
                current_data=current_data,
                new_data=new_data,
                command_name=command_name,
                realm=realm,
            )

            self.diff_reporter.display_summary(diff_result)

            return diff_result

        except Exception as e:
            error(f"Quick diff failed: {str(e)}")
            return None


def create_diff_manager() -> DiffManager:
    """Factory function to create a DiffManager instance"""
    return DiffManager()


# Convenience functions for common diff operations
def diff_journeys(
    file_path: Optional[str] = None,
    realm: str = DEFAULT_REALM,
    branch: Optional[str] = None,
    **auth_params,
) -> Optional[DiffResult]:
    """Convenience function for journeys diff"""
    manager = create_diff_manager()
    return manager.perform_diff(
        command_name="journeys",
        file_path=file_path,
        realm=realm,
        branch=branch,
        **auth_params,
    )


def diff_scripts(
    file_path: Optional[str] = None,
    realm: str = DEFAULT_REALM,
    branch: Optional[str] = None,
    **auth_params,
) -> Optional[DiffResult]:
    """Convenience function for scripts diff"""
    manager = create_diff_manager()
    return manager.perform_diff(
        command_name="scripts",
        file_path=file_path,
        realm=realm,
        branch=branch,
        **auth_params,
    )


def diff_services(
    file_path: Optional[str] = None,
    realm: str = DEFAULT_REALM,
    branch: Optional[str] = None,
    **auth_params,
) -> Optional[DiffResult]:
    """Convenience function for services diff"""
    manager = create_diff_manager()
    return manager.perform_diff(
        command_name="services",
        file_path=file_path,
        realm=realm,
        branch=branch,
        **auth_params,
    )


def diff_managed(
    file_path: Optional[str] = None,
    branch: Optional[str] = None,
    **auth_params,
) -> Optional[DiffResult]:
    """Convenience function for managed objects diff"""
    manager = create_diff_manager()
    return manager.perform_diff(
        command_name="managed",
        file_path=file_path,
        branch=branch,
        **auth_params,
    )
