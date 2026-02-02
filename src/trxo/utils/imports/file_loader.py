"""
File loader for import operations.

Handles loading data from local files and Git repositories.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from trxo.utils.console import error, info, warning
from trxo.utils.git import GitManager
from .component_mapper import ComponentMapper


class FileLoader:
    """Handles loading data from local and Git sources"""

    @staticmethod
    def load_from_local_file(file_path: str) -> List[Dict[str, Any]]:
        """
        Load and validate data from local JSON file.

        Args:
            file_path: Path to JSON file

        Returns:
            List of items from the file

        Raises:
            ValueError: If file format is invalid
            FileNotFoundError: If file doesn't exist
        """
        try:
            # Convert to absolute path if relative
            import os

            if not os.path.isabs(file_path):
                file_path = os.path.abspath(file_path)

            # Check if file exists
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            # Read and parse JSON file
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Validate JSON structure
            if not isinstance(data, dict):
                raise ValueError("Invalid JSON structure: Root should be an object")

            # Check for expected structure
            if "data" not in data:
                raise ValueError("Invalid JSON structure: Missing 'data' field")

            # Support both collection (data.result = [...]) and single-object (data = {...}) shapes
            if "result" in data["data"]:
                items = data["data"]["result"]
                if not isinstance(items, list):
                    raise ValueError(
                        "Invalid JSON structure: 'data.result' should be an array"
                    )
            else:
                # No 'result' array; accept a single object and wrap it
                if isinstance(data["data"], dict):
                    items = [data["data"]]
                else:
                    raise ValueError(
                        "Invalid JSON structure: 'data' must be an object or contain 'result' array"
                    )

            return items

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")
        except Exception as e:
            raise Exception(f"Error loading file: {str(e)}")

    @staticmethod
    def load_from_git_file(file_path: Path) -> List[Dict[str, Any]]:
        """
        Load and parse a JSON file from Git repository.

        Args:
            file_path: Path to JSON file in Git repo

        Returns:
            List of items from the file
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Handle Git export format with metadata structure
            if isinstance(data, dict):
                if "data" in data:
                    # Git export format: {"metadata": {...}, "data": {"result": [...]}}
                    data_section = data["data"]
                    if isinstance(data_section, dict) and "result" in data_section:
                        # Extract the result array
                        result = data_section["result"]
                        return result if isinstance(result, list) else [result]
                    elif isinstance(data_section, list):
                        # Direct list in data section
                        return data_section
                    else:
                        # Single item in data section
                        return [data_section]
                else:
                    # Direct data format (backward compatibility)
                    return [data]
            elif isinstance(data, list):
                # Direct list format
                return data
            else:
                warning(f"Unexpected data format in {file_path.name}")
                return []

        except json.JSONDecodeError as e:
            error(f"Invalid JSON in {file_path.name}: {e}")
            return []
        except Exception as e:
            error(f"Failed to read {file_path.name}: {e}")
            return []

    @staticmethod
    def discover_git_files(
        repo_path: Path, item_type: str, realm: Optional[str]
    ) -> List[Path]:
        """
        Discover files in Git repository based on item type and realm.

        Args:
            repo_path: Path to Git repository
            item_type: Type of items to discover
            realm: Realm to search in (None for all realms)

        Returns:
            List of discovered file paths
        """
        discovered_files = []
        component = ComponentMapper.get_component_directory(item_type)

        if realm:
            # Search in specific realm
            realm_component_dir = repo_path / realm / component
            if realm_component_dir.exists():
                for json_file in realm_component_dir.glob("*.json"):
                    discovered_files.append(json_file)
                    info(f"Found: {json_file.relative_to(repo_path)}")
        else:
            # Search in all realms
            for realm_dir in repo_path.iterdir():
                if realm_dir.is_dir() and not realm_dir.name.startswith("."):
                    component_dir = realm_dir / component
                    if component_dir.exists():
                        for json_file in component_dir.glob("*.json"):
                            discovered_files.append(json_file)
                            info(f"Found: {json_file.relative_to(repo_path)}")

        return discovered_files

    @staticmethod
    def load_git_files(
        git_manager: GitManager,
        item_type: str,
        realm: Optional[str],
        branch: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Load data from Git repository with intelligent file discovery.

        Args:
            git_manager: Git manager instance
            item_type: Type of items to load
            realm: Realm to load from
            branch: Git branch (for display purposes)

        Returns:
            List of all items from discovered files
        """
        repo_path = Path(git_manager.local_path)

        # Discover files in Git repository
        discovered_files = FileLoader.discover_git_files(repo_path, item_type, realm)

        if not discovered_files:
            return []

        # Load and combine data from discovered files
        all_items = []
        for file_path in discovered_files:
            try:
                info(f"Loading from: {file_path.relative_to(repo_path)}")
                items = FileLoader.load_from_git_file(file_path)
                all_items.extend(items)
            except Exception as e:
                warning(f"Failed to load {file_path.name}: {e}")
                continue

        return all_items
