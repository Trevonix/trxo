"""
File saver for local storage with versioning support.

Handles saving exported data to local files with automatic versioning.
"""

import time
import json
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from tqdm import tqdm
from trxo.utils.console import info, error


class FileSaver:
    """Handles local file saving with versioning"""

    @staticmethod
    def build_versioned_filename(
        command_name: str,
        realm_prefix: Optional[str],
        version_tag: str,
        timestamp: str
    ) -> str:
        """
        Build a versioned filename.

        Args:
            command_name: Command name
            realm_prefix: Optional realm prefix
            version_tag: Version tag (e.g., 'v1')
            timestamp: Timestamp string

        Returns:
            Filename string
        """
        base_name = f"{command_name}_{version_tag}_{timestamp}.json"
        if realm_prefix:
            return f"{realm_prefix}_{base_name}"
        return base_name

    @staticmethod
    def determine_next_version(
        output_dir: Optional[str],
        versioning_id: str
    ) -> int:
        """
        Determine next version number by scanning existing files.

        Args:
            output_dir: Output directory path
            versioning_id: Stable versioning identifier

        Returns:
            Next version number
        """
        auto_n = 1

        try:
            # Try using py-file-versioning first
            from py_file_versioning import FileVersioning, FileVersioningConfig, CompressionType

            ledger_dir = (Path(output_dir) / ".trxo_versions"
                          if output_dir
                          else Path(".trxo_versions")
                          )
            ledger_dir.mkdir(parents=True, exist_ok=True)

            config = FileVersioningConfig(
                versioned_path=str(ledger_dir),
                compression=CompressionType.NONE,
                max_count=5,
                max_versions=5
            )
            fv = FileVersioning(config)

            stable_base_id = f"{versioning_id}.json"
            existing = fv.list_versions(stable_base_id)
            auto_n = len(existing) + 1

            # Create version record (temp file approach)
            tmp_dir = Path(tempfile.mkdtemp())
            tmp_file = tmp_dir / stable_base_id
            tmp_file.write_text(json.dumps({"placeholder": True}), encoding="utf-8")
            fv.create_version(str(tmp_file))
            shutil.rmtree(tmp_dir)

        except Exception:
            # Fallback: scan existing files
            try:
                output_path = Path(output_dir) if output_dir else Path(".")
                if output_path.exists():
                    pattern = f"{versioning_id}_v*_*.json"
                    existing_files = list(output_path.glob(pattern))

                    if existing_files:
                        versions = []
                        for file_obj in existing_files:
                            try:
                                parts = file_obj.stem.split('_')
                                for part in parts:
                                    if part.startswith('v') and part[1:].isdigit():
                                        versions.append(int(part[1:]))
                                        break
                            except (ValueError, IndexError):
                                continue

                        if versions:
                            auto_n = max(versions) + 1
            except Exception:
                pass

        return auto_n

    @staticmethod
    def save_with_progress(
        data: Dict[str, Any],
        file_path: Path,
        filename: str
    ) -> bool:
        """
        Save data to file with progress bar.

        Args:
            data: Data to save
            file_path: Full file path
            filename: Display filename

        Returns:
            True if successful, False otherwise
        """
        try:
            with tqdm(
                total=100,
                desc=f"💾 Exporting {filename}",
                bar_format="{l_bar}{bar:40}{r_bar}{bar:-40b}",
                colour="green",
                ncols=100,
                leave=True,
            ) as pbar:
                pbar.set_description("💾 Preparing data")
                pbar.update(20)
                time.sleep(0.2)

                pbar.set_description("📁 Creating file")
                pbar.update(30)
                time.sleep(0.2)

                pbar.set_description("✍️  Writing data")
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                pbar.update(40)
                time.sleep(0.2)

                pbar.set_description("✅ Finalizing")
                pbar.update(10)
                time.sleep(0.1)

                pbar.set_description(f"✅ Saved {filename}")

            info(f"📁 Exported to: {file_path.resolve()}")
            return True

        except Exception as e:
            error(f"Failed to save file: {str(e)}")
            return False

    @staticmethod
    def save_to_local(
        data: Dict[Any, Any],
        command_name: str,
        output_dir: Optional[str] = None,
        output_file: Optional[str] = None,
        version: Optional[str] = None,
        no_version: bool = False,
    ) -> Optional[str]:
        """
        Save data to local storage with versioning.

        Args:
            data: Data to save
            command_name: Command name
            output_dir: Output directory
            output_file: Custom output filename
            version: Custom version name
            no_version: Disable versioning

        Returns:
            Full path to saved file, or None if failed
        """
        # Extract realm from metadata
        realm_prefix = None
        if isinstance(data, dict) and isinstance(data.get("metadata"), dict):
            realm_prefix = data["metadata"].get("realm")

        # Normalize component name
        component = command_name
        if command_name.startswith("services_realm_"):
            component = "services"
            if not realm_prefix:
                realm_prefix = command_name.split("services_realm_")[-1]
        elif command_name == "services_global":
            component = "services"

        # Base component for versioning
        base_component = output_file or component

        # Create stable versioning identifier
        versioning_id = base_component
        if realm_prefix:
            versioning_id = f"{realm_prefix}_{base_component}"

        # Timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Determine version tag
        if no_version:
            version_tag = output_file or component
            filename = f"{versioning_id}_{timestamp}.json"
        else:
            if version:
                version_tag = version
            else:
                auto_n = FileSaver.determine_next_version(output_dir, versioning_id)
                version_tag = f"v{auto_n}"

            filename = FileSaver.build_versioned_filename(
                base_component, realm_prefix, version_tag, timestamp
            )

        # Determine output path
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            file_path = output_path / filename
        else:
            file_path = Path(filename)

        # Update metadata with version
        if isinstance(data, dict):
            meta = data.setdefault("metadata", {})
            meta["version"] = version_tag
            meta.setdefault("timestamp", datetime.now(timezone.utc).isoformat())

        # Save with progress bar
        if FileSaver.save_with_progress(data, file_path, filename):
            return str(file_path.resolve())

        return None
