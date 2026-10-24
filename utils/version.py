"""Version management utilities for xc-ce-utils."""

import json
import re
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as dist_version
from pathlib import Path
from typing import Any, Dict, Optional

from packaging.version import Version


class VersionManager:
    """Manages xc-ce-utils version information."""

    def __init__(self):
        self._version_dict: Optional[Dict] = None
        self._version_obj: Optional[Version] = None

    def load_version(self) -> Dict[str, Any]:
        """Load version from version.json.

        Returns:
            Dict with MAJOR_VERSION, MINOR_VERSION, BUGFIX_VERSION
        """
        if self._version_dict is not None:
            return self._version_dict

        # Determine candidate locations (frozen, source checkout, installed wheel)
        current_file = Path(__file__).resolve()
        package_dir = current_file.parent.parent  # xc_ce_utils/
        project_root = package_dir.parent

        if getattr(sys, 'frozen', False):
            base_path = Path(str(sys.__dict__.get('_MEIPASS')))
            version_candidates = [
                base_path / 'config' / 'versioning' / 'version.json',
                base_path / 'versioning' / 'version.json',
            ]
        else:
            # 1) source checkout root/config/versioning/version.json
            # 2) installed wheel data-file under <venv>/config/versioning/version.json
            # 3) package-local fallback (for unusual layouts)
            version_candidates = [
                project_root / 'config' / 'versioning' / 'version.json',
                Path(sys.prefix) / 'config' / 'versioning' / 'version.json',
                package_dir / 'config' / 'versioning' / 'version.json',
            ]

        version_file = next((p for p in version_candidates if p.exists()), None)

        if version_file is None:
            # Fallback for wheel installs where config data is unavailable:
            # derive MAJOR/MINOR/BUGFIX[/PRE_RELEASE_SUFFIX] from installed package metadata.
            dist_errors = []
            for package_name in ('xc-ce-utils', 'xc_ce_utils'):
                try:
                    installed_version = dist_version(package_name)
                    match = re.match(
                        r'^(\d+)\.(\d+)\.(\d+)(.*)$', installed_version
                    )
                    if match:
                        prerelease_suffix = match.group(4) or ''
                        self._version_dict = {
                            'MAJOR_VERSION': int(match.group(1)),
                            'MINOR_VERSION': int(match.group(2)),
                            'BUGFIX_VERSION': int(match.group(3)),
                            'PRE_RELEASE_SUFFIX': prerelease_suffix,
                        }
                        return self._version_dict
                except PackageNotFoundError as exc:
                    dist_errors.append(f'{package_name}: {exc}')

            checked_paths = ', '.join(str(p) for p in version_candidates)
            raise FileNotFoundError(
                "Version file not found in any known location, and package metadata "
                "could not be resolved. "
                f"Checked: {checked_paths}. "
                f"Frozen: {getattr(sys, 'frozen', False)}. "
                f"sys.prefix: {Path(sys.prefix)}. "
                f"sys._MEIPASS: {sys.__dict__.get('_MEIPASS', 'N/A')}. "
                f"Metadata errors: {dist_errors}"
            )

        try:
            with open(
                version_file, 'r', encoding='utf-8-sig'
            ) as f:  # utf-8-sig handles BOM
                content = f.read()
                if not content or content.strip() == '':
                    raise ValueError(f'Version file is empty: {version_file}')
                self._version_dict = json.loads(content)
            return self._version_dict
        except json.JSONDecodeError as e:
            # Read raw bytes to debug encoding issues
            with open(version_file, 'rb') as f:
                raw_content = f.read()
            raise ValueError(
                f"Invalid JSON in version file {version_file}: {e}\nFile size: {version_file.stat().st_size} bytes\nFirst 100 bytes (raw): {raw_content[:100]}\nFirst 100 chars (decoded): {raw_content[:100].decode('utf-8', errors='replace')}"
            ) from e
        except Exception as e:
            raise RuntimeError(
                f'Failed to load version file {version_file}: {e}'
            ) from e

    def get_version_string(self) -> str:
        """Get semantic version string (e.g., '4.3.0' or '5.3.0b0').

        Returns:
            Version string in format MAJOR.MINOR.BUGFIX[PRE_RELEASE_SUFFIX]
        """
        version_dict = self.load_version()
        prerelease_suffix = str(version_dict.get('PRE_RELEASE_SUFFIX', ''))
        return f"{version_dict['MAJOR_VERSION']}.{version_dict['MINOR_VERSION']}.{version_dict['BUGFIX_VERSION']}{prerelease_suffix}"

    def get_version_object(self) -> Version:
        """Get packaging.version.Version object for comparison.

        Returns:
            Version object for semantic version comparison
        """
        if self._version_obj is None:
            self._version_obj = Version(self.get_version_string())
        return self._version_obj

    def get_major_version_suffix(self) -> str:
        """Get major version suffix for folder naming (e.g., '4.x').

        Returns:
            Version string in format MAJOR.x (for folder suffix)
        """
        version_dict = self.load_version()
        return f"{version_dict['MAJOR_VERSION']}.x"


# Singleton instance
version_manager = VersionManager()
