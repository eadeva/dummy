"""
Enhanced Artifactory Installer with Performance Optimizations

This module uses the enhanced downloader for faster dependency installation.

Key improvements:
- Batch downloads with single AQL query
- Parallel installation of multiple dependencies
- Centralized caching
- Better error handling and progress reporting
"""

import asyncio
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add the parent directory to the Python path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from xc_ce_utils.artifactory_utils.artifactory_downloader import (
    ArtifactoryDownloader,
)
from xc_ce_utils.core_engine.domain.runtime_context import get_runtime_context
from xc_ce_utils.global_modules.aux_helper import unzip_7z
from xc_ce_utils.rb_logger.rb_logger import logger


class ArtifactoryInstaller:
    """
    Enhanced Artifactory installer with batch operations and parallel downloads.

    Features:
    - Batch processing of multiple dependencies
    - Parallel downloads using async/await
    - Smart caching to avoid redundant queries
    - Better progress tracking
    """

    def __init__(
        self,
        artifactories: Dict[str, Any],
        action: Optional[str] = None,
        env_path: Optional[Path] = None,
        base_download_path: Optional[str] = None,
        env_var_prefix: Optional[str] = 'ARTIFACT',
        cache_ttl: int = 3600,
        max_concurrent_downloads: int = 10,
        append: bool = False,
    ):
        """
        Initialize the enhanced installer.

        Args:
            artifactories: Dictionary of Artifactory configurations
            action: Build action to filter dependencies
            env_path: Path to .env file
            base_download_path: Base path for downloads
            env_var_prefix: Prefix for environment variables
            cache_ttl: Cache time-to-live in seconds
            max_concurrent_downloads: Maximum parallel downloads
            append: If True, append to existing env file instead of recreating it
        """
        self.repo_root_dir = Path().cwd()
        self.action = action.lower() if action else None
        self.env_file_path = (
            env_path if env_path else self.repo_root_dir / '.env'
        )

        if not append and self.env_file_path.exists():
            self.env_file_path.unlink()

        self.env_prefix = env_var_prefix
        self.artifactories = artifactories
        self.cache_ttl = cache_ttl
        self.max_concurrent_downloads = max_concurrent_downloads
        self.runtime_context = get_runtime_context()

        # Set the default download path based on OS
        if not base_download_path:
            if platform.system() == 'Windows':
                if platform.node().lower() == 'si0vm13380':
                    self.base_download_path = Path('D:\\') / 'tools'
                else:
                    self.base_download_path = Path('C:\\') / 'tools'
            else:
                self.base_download_path = Path(os.environ['HOME']) / 'tools'
        else:
            self.base_download_path = Path(base_download_path)

    def filter_artifacts_by_action(
        self, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Filter artifacts based on the current action.

        Args:
            config: Full artifact configuration

        Returns:
            Filtered configuration containing only needed artifacts
        """
        if not self.action:
            return config

        filtered = {}
        for tool, details in config.items():
            needed_for = details.get('needed_for', [])
            if not needed_for or self.action in needed_for:
                filtered[tool] = details

        return filtered

    @staticmethod
    def _normalize_os_name(value: Any) -> str:
        """Normalize dependency os field (default: windows)."""
        if value is None:
            return 'windows'
        normalized = str(value).strip().lower()
        return normalized or 'windows'

    @staticmethod
    def _as_bool(value: Any, default: bool = False) -> bool:
        """Convert configuration value to bool."""
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        normalized = str(value).strip().lower()
        if normalized in {'1', 'true', 'yes', 'on', 'enable', 'enabled'}:
            return True
        if normalized in {'0', 'false', 'no', 'off', 'disable', 'disabled'}:
            return False
        return default

    def _is_download_allowed_for_runtime(
        self, dep_name: str, dep_details: Dict[str, Any]
    ) -> bool:
        """Return True if remote download is allowed for current runtime context.

        Defaults:
        - os: windows
        - on-docker: false
        """
        required_os = self._normalize_os_name(dep_details.get('os', 'windows'))
        current_os = self.runtime_context.os_name

        if current_os != required_os:
            logger.info(
                f'Skipping {dep_name}: unsupported os (required={required_os}, current={current_os})'
            )
            return False

        download_on_docker = self._as_bool(
            dep_details.get('on-docker', False), default=False
        )
        if self.runtime_context.is_docker and not download_on_docker:
            logger.info(
                f'Skipping {dep_name}: download disabled in docker (on-docker=false)'
            )
            return False

        return True

    def download_dependencies_from_config(
        self, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Download dependencies using enhanced batch operations.

        Args:
            config: Artifact configuration dictionary

        Returns:
            The configuration used for downloading
        """
        filtered_config = self.filter_artifacts_by_action(config)

        if not filtered_config:
            logger.info('No dependencies to download for this action')
            return {}

        logger.log_phase_header(
            f'{self.env_prefix} INSTALLER - STARTED (ENHANCED)'
        )
        start_time = time.time()

        # Group dependencies by artifactory instance for batch processing
        artifactory_groups = self._group_by_artifactory(filtered_config)

        all_results = []
        env_variables = {}
        tcc_errors = []

        # Process each artifactory group
        for artifactory_key, dependencies in artifactory_groups.items():
            artifactory_conf = self.artifactories[artifactory_key]
            artifactory_url = artifactory_conf['url']
            repository = artifactory_conf['repository']
            # Prepare artifact specifications for batch download
            artifact_specs = []
            tcc_tools_specs = []
            local_override_count = 0
            skipped_runtime_count = 0

            for dep_name, dep_details in dependencies.items():
                # --- CLI override check via --artifact flag ---
                env_key = dep_name.upper().replace('-', '_')
                artifact_source = os.environ.get(f'ARTIFACT_{env_key}_SOURCE')

                if artifact_source == 'local':
                    local_path = os.environ.get(f'ARTIFACT_{env_key}', '')
                    logger.info(
                        f'Using local artifact override for {dep_name}: {local_path}'
                    )
                    local_override_count += 1
                    version = dep_details.get('properties', {}).get(
                        'rb_version'
                    )
                    all_results.append(
                        (dep_name, Path(local_path), False, version)
                    )
                    dep_env_var = f'{self.env_prefix}_{env_key}'
                    env_variables[dep_env_var] = local_path
                    if version:
                        env_variables[f'{dep_env_var}_VERSION'] = version
                    continue

                if not self._is_download_allowed_for_runtime(
                    dep_name, dep_details
                ):
                    skipped_runtime_count += 1
                    continue

                if artifact_source == 'remote':
                    override_version = os.environ.get(
                        f'ARTIFACT_{env_key}_VERSION'
                    )
                    if override_version:
                        dep_details = dict(dep_details)  # shallow copy
                        props = dict(dep_details.get('properties', {}))
                        props['rb_version'] = override_version
                        dep_details['properties'] = props
                        logger.info(
                            f'Artifact version override for {dep_name}: {override_version}'
                        )

                # Get download path
                download_path = self._get_download_path_from_properties(
                    dep_name, dep_details, repository
                )

                # Prepare spec
                rel_path = dep_details.get('download_rel_dir', '')
                if rel_path:
                    rel_path = f'{rel_path}/{dep_name}'
                else:
                    rel_path = dep_name

                if repository == 'tcc-tools-local':
                    # Special handling for tcc-tools-local: use direct pattern-based download
                    # Keep version in path, download_path already contains it from _get_download_path_from_properties
                    version = dep_details['properties']['rb_version']
                    download_rel_path = (
                        f'ZippedTools/{dep_name}/{dep_name}_{version}*'
                    )

                    tcc_spec = {
                        'name': dep_name,
                        'rel_path': download_rel_path,
                        'download_path': download_path,
                        'details': dep_details,
                        'version': version,
                    }
                    tcc_tools_specs.append(tcc_spec)
                else:
                    spec = {
                        'name': dep_name,
                        'rel_path': rel_path,
                        'properties': dep_details.get('properties', {}),
                        'download_path': download_path,
                        'details': dep_details,
                    }
                    artifact_specs.append(spec)

            eligible_remote_count = len(artifact_specs) + len(tcc_tools_specs)
            logger.info(
                f'{artifactory_key}/{repository}: total={len(dependencies)}, '
                f'eligible_remote={eligible_remote_count}, '
                f'local_overrides={local_override_count}, '
                f'skipped_by_runtime={skipped_runtime_count}'
            )

            if eligible_remote_count == 0:
                continue

            # Create enhanced downloader only when at least one remote dependency is eligible.
            with ArtifactoryDownloader(
                artifactory_url,
                repository,
                cache_ttl=self.cache_ttl,
                max_concurrent_downloads=self.max_concurrent_downloads,
            ) as downloader:
                # Batch download all artifacts from this Artifactory
                if artifact_specs:
                    results = self._download_batch(downloader, artifact_specs)
                    all_results.extend(results)

                    # Collect environment variables
                    for dep_name, download_path, downloaded, version in results:
                        if download_path:
                            env_var = f'{self.env_prefix}_{dep_name.upper()}'
                            env_variables[env_var] = str(download_path)
                            if version:
                                env_variables[f'{env_var}_VERSION'] = version

                # Process tcc-tools-local dependencies separately (synchronous, pattern-based)
                tcc_errors = []
                if tcc_tools_specs:
                    logger.info(
                        f'Processing {len(tcc_tools_specs)} tcc-tools-local dependencies...'
                    )

                    for tcc_spec in tcc_tools_specs:
                        try:
                            result = self._download_tcc_tools_sync(
                                downloader, tcc_spec
                            )
                            all_results.append(result)

                            # Collect environment variables for successful downloads
                            dep_name, download_path, downloaded, version = (
                                result
                            )
                            if download_path:
                                env_var = (
                                    f'{self.env_prefix}_{dep_name.upper()}'
                                )
                                env_variables[env_var] = str(download_path)
                                if version:
                                    env_variables[f'{env_var}_VERSION'] = (
                                        version
                                    )
                        except Exception as e:
                            tcc_errors.append((tcc_spec['name'], str(e)))

        # Write all environment variables to file
        if env_variables:
            with self.env_file_path.open('a') as env_file:
                for var_name, var_value in env_variables.items():
                    normalized_path = var_value.replace('\\', '/')
                    env_file.write(f'{var_name}={normalized_path}\n')

        # Log summary
        downloaded = [name for name, _, dl, _ in all_results if dl]
        existing = [name for name, _, dl, _ in all_results if not dl and name]

        if downloaded:
            logger.info(
                f"{self.env_prefix} newly installed: {', '.join(downloaded)}"
            )
        if existing:
            logger.info(
                f"{self.env_prefix} already existing: {', '.join(existing)}"
            )

        elapsed_time = time.time() - start_time
        minutes, seconds = divmod(elapsed_time, 60)

        if minutes > 0:
            logger.progress(
                f'Downloads completed in {int(minutes)}m {seconds:.1f}s'
            )
        else:
            logger.progress(f'Downloads completed in {seconds:.1f}s')

        # Check for tcc-tools-local errors and raise at the end
        if tcc_errors:
            error_msg = 'Failed to download tcc-tools-local dependencies:\n'
            for tool_name, error in tcc_errors:
                error_msg += f'  - {tool_name}: {error}\n'
            logger.error(error_msg)
            logger.log_phase_header(f'{self.env_prefix} INSTALLER - FAILED')
            raise Exception(error_msg)

        logger.success(f'{self.env_prefix} installer finished successfully')
        logger.log_phase_header(f'{self.env_prefix} INSTALLER - DONE')

        return config

    def _group_by_artifactory(
        self, config: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Group dependencies by Artifactory instance.

        Args:
            config: Artifact configuration

        Returns:
            Dictionary mapping artifactory keys to their dependencies
        """
        groups = {}

        for dep_name, dep_details in config.items():
            artifactory_key = dep_details.get('artifactory')
            if not artifactory_key:
                logger.warning(
                    f'No artifactory specified for {dep_name}, skipping'
                )
                continue

            if artifactory_key not in groups:
                groups[artifactory_key] = {}

            groups[artifactory_key][dep_name] = dep_details

        return groups

    def _download_tcc_tools_sync(
        self, downloader: ArtifactoryDownloader, spec: Dict[str, Any]
    ) -> Tuple[str, Optional[Path], bool, Optional[str]]:
        """
        Download and extract a tcc-tools-local dependency synchronously.

        Uses pattern-based download without property filtering,
        then handles .zip or .001 multi-part archive extraction.

        Args:
            downloader: Artifactory downloader instance
            spec: Artifact specification containing name, rel_path, download_path, version

        Returns:
            Tuple of (name, path, downloaded, version)

        Raises:
            Exception: If download or extraction fails
        """
        dep_name = spec['name']
        download_path = spec['download_path']
        download_rel_path = spec['rel_path']
        version = spec['version']

        # Check if already exists; marker-only folders are treated as incomplete.
        if download_path.exists():
            payload_entries = [
                p
                for p in download_path.iterdir()
                if p.name != '.artifact_meta.json'
            ]
            if payload_entries:
                logger.info(f'{dep_name} already exists at {download_path}')
                # Ensure .artifact_meta.json exists for reporting
                meta_file = download_path / '.artifact_meta.json'
                if not meta_file.exists():
                    meta = {
                        'name': dep_name,
                        'created': '',
                        'download_url': '',
                        'properties': {'rb_version': version},
                    }
                    meta_file.write_text(json.dumps(meta, indent=2))
                return dep_name, download_path, False, version

            logger.warning(
                f'{dep_name} found only metadata marker at {download_path}; re-downloading'
            )
            import shutil

            shutil.rmtree(download_path)

        # Create download directory
        download_path.mkdir(parents=True, exist_ok=True)

        try:
            # Download using pattern-based method
            logger.progress(
                f'Downloading {dep_name} from pattern {download_rel_path}...'
            )
            downloaded_files = downloader.download_from_pattern(
                download_rel_path, download_path
            )

            if not downloaded_files:
                raise Exception(f'No files downloaded for {dep_name}')

            # Extract downloaded files - try .zip first, then .001 multi-part
            tool_zip_file = download_path / f'{dep_name}_{version}.zip'

            if tool_zip_file.exists():
                logger.progress(
                    f'Unzipping tool {dep_name} version {version}...'
                )
                unzip_7z(
                    str(tool_zip_file),
                    str(download_path),
                    remove_original_zip=True,
                )
                logger.success(f'Extracted {dep_name} from .zip archive')
            else:
                # Try multi-part .001 archive
                tool_zip_file = download_path / f'{dep_name}_{version}.001'

                if tool_zip_file.exists():
                    logger.progress(
                        f'Unzipping tool {dep_name} version {version} (multi-part archive)...'
                    )
                    unzip_7z(
                        str(tool_zip_file),
                        str(download_path),
                        remove_original_zip=False,
                    )

                    # Clean up multi-part archive files (.001, .002, etc.)
                    for file in download_path.glob(f'{dep_name}_{version}.00*'):
                        if file.is_file():
                            file.unlink()
                            logger.debug(
                                f'Removed multi-part file: {file.name}'
                            )

                    logger.success(
                        f'Extracted {dep_name} from multi-part archive'
                    )
                else:
                    raise Exception(
                        f'Tool {dep_name} version {version} downloaded file not supported. '
                        f'Expected .zip or .001 file, but neither found.'
                    )

            payload_entries = [
                p
                for p in download_path.iterdir()
                if p.name != '.artifact_meta.json'
            ]
            if not payload_entries:
                raise Exception(
                    f'Extraction produced no payload files for {dep_name} at {download_path}'
                )

            # Write .artifact_meta.json for tcc-tools
            meta = {
                'name': dep_name,
                'created': '',
                'download_url': '',
                'properties': {'rb_version': version},
            }
            meta_file = download_path / '.artifact_meta.json'
            meta_file.write_text(json.dumps(meta, indent=2))

            return dep_name, download_path, True, version

        except Exception as e:
            # Clean up on failure
            if download_path.exists():
                import shutil

                shutil.rmtree(download_path)
                logger.debug(
                    f'Cleaned up failed download directory: {download_path}'
                )
            raise Exception(f'Failed to download/extract {dep_name}: {e}')

    def _download_batch(
        self,
        downloader: ArtifactoryDownloader,
        artifact_specs: List[Dict[str, Any]],
    ) -> List[Tuple[str, Optional[Path], bool, Optional[str]]]:
        """
        Download a batch of artifacts in parallel.

        Args:
            downloader: Enhanced downloader instance
            artifact_specs: List of artifact specifications

        Returns:
            List of (name, path, downloaded, version) tuples
        """
        results = []
        failed_downloads = []

        # Use asyncio for parallel downloads
        async def download_all():
            tasks = []
            for spec in artifact_specs:
                task = self._download_single_async(downloader, spec)
                tasks.append(task)

            return await asyncio.gather(*tasks, return_exceptions=True)

        # Run the async downloads
        async_results = asyncio.run(download_all())

        # Process results
        for i, result in enumerate(async_results):
            if isinstance(result, Exception):
                dep_name = artifact_specs[i]['name']
                logger.error(f'Error downloading {dep_name}: {result}')
                # Track as failed, not as "existing"
                failed_downloads.append((dep_name, str(result)))
            else:
                results.append(result)

        # If there are failed downloads, raise an error
        if failed_downloads:
            error_msg = 'Failed to download the following artifacts:\n'
            for name, error in failed_downloads:
                error_msg += f'  - {name}: {error}\n'
            raise Exception(error_msg)

        return results

    async def _download_single_async(
        self, downloader: ArtifactoryDownloader, spec: Dict[str, Any]
    ) -> Tuple[str, Optional[Path], bool, Optional[str]]:
        """
        Download a single dependency asynchronously.

        Args:
            downloader: Enhanced downloader
            spec: Artifact specification

        Returns:
            Tuple of (name, path, downloaded, version)
        """
        dep_name = spec['name']
        download_path = spec['download_path']
        details = spec['details']
        no_cache = bool(details.get('no-cache', details.get('no_cache', False)))

        # Check if already exists; marker-only folders are treated as incomplete.
        if download_path.exists():
            version = details.get('properties', {}).get('rb_version')
            payload_entries = [
                p
                for p in download_path.iterdir()
                if p.name != '.artifact_meta.json'
            ]

            if payload_entries:
                # Ensure .artifact_meta.json exists for reporting
                meta_file = download_path / '.artifact_meta.json'
                if not meta_file.exists():
                    # Query Artifactory for real properties
                    rel_path = spec['rel_path']
                    properties = spec.get('properties', {})
                    artifact_properties = {}
                    try:
                        artifacts = downloader.get_artifacts_by_properties_fast(
                            rel_path,
                            properties,
                            read_cache=not no_cache,
                            write_cache=not no_cache,
                        )
                        if artifacts:
                            latest = downloader._select_latest_artifact(
                                artifacts
                            )
                            if 'properties' in latest:
                                for prop in latest['properties']:
                                    artifact_properties[prop.get('key', '')] = (
                                        prop.get('value', '')
                                    )
                    except Exception:
                        artifact_properties = (
                            {'rb_version': version} if version else {}
                        )
                    meta = {
                        'name': dep_name,
                        'created': '',
                        'download_url': '',
                        'properties': artifact_properties
                        or ({'rb_version': version} if version else {}),
                    }
                    meta_file.write_text(json.dumps(meta, indent=2))
                return dep_name, download_path, False, version

            logger.warning(
                f'{dep_name} found only metadata marker at {download_path}; re-downloading'
            )
            import shutil

            shutil.rmtree(download_path)

        try:
            # Use the enhanced downloader's async method
            # For now, we'll use a thread pool to run sync code async
            loop = asyncio.get_event_loop()

            def do_download():
                rel_path = spec['rel_path']
                properties = spec['properties']

                # Find artifacts
                artifacts = downloader.get_artifacts_by_properties_fast(
                    rel_path,
                    properties,
                    read_cache=not no_cache,
                    write_cache=not no_cache,
                )

                if not artifacts:
                    raise Exception(
                        f'No artifacts found for {dep_name} with properties {properties}'
                    )

                # Get latest
                latest = downloader._select_latest_artifact(artifacts)

                # Download
                download_path.mkdir(parents=True, exist_ok=True)

                artifact_path = latest['path']
                artifact_name = latest['name']
                download_url = f'{downloader.base_repo_url}/{artifact_path}/{artifact_name}'

                target_file = download_path / artifact_name

                logger.progress(f'Downloading {dep_name}...')
                response = downloader.session.get(download_url, stream=True)
                response.raise_for_status()

                with target_file.open('wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                logger.success(f'Downloaded {dep_name}')

                # Extract if needed
                if target_file.suffix.lower() in ['.zip', '.7z', '.gz', '.bz2']:
                    from xc_ce_utils.global_modules.aux_helper import unzip_file

                    logger.progress(f'Extracting {artifact_name}...')
                    unzip_file(str(target_file), str(download_path))
                    target_file.unlink()

                payload_entries = [
                    p
                    for p in download_path.iterdir()
                    if p.name != '.artifact_meta.json'
                ]
                if not payload_entries:
                    raise Exception(
                        f'Extraction produced no payload files for {dep_name} at {download_path}'
                    )

                # Write .artifact_meta.json with real properties from Artifactory
                artifact_properties = {}
                if 'properties' in latest:
                    for prop in latest['properties']:
                        artifact_properties[prop.get('key', '')] = prop.get(
                            'value', ''
                        )
                meta = {
                    'name': artifact_name,
                    'created': latest.get('created', ''),
                    'download_url': download_url,
                    'properties': artifact_properties,
                }
                meta_file = download_path / '.artifact_meta.json'
                meta_file.write_text(json.dumps(meta, indent=2))

                version = properties.get('rb_version')
                return dep_name, download_path, True, version

            # Run in thread pool
            result = await loop.run_in_executor(None, do_download)
            return result

        except Exception as e:
            logger.error(f'Error downloading {dep_name}: {e}')
            if download_path.exists():
                import shutil

                shutil.rmtree(download_path)
            raise

    def _get_download_path_from_properties(
        self,
        dependency_name: str,
        dependency_details: Dict[str, Any],
        repository: str,
    ) -> Path:
        """
        Construct download path from dependency properties.

        Args:
            dependency_name: Name of dependency
            dependency_details: Dependency configuration
            repository: Repository name

        Returns:
            Download path
        """
        properties = dependency_details.get('properties', {})

        if 'rb_version' not in properties:
            raise Exception(f"'rb_version' required for {dependency_name}")

        dep_type = dependency_details.get('target_dir', 'rb_artifacts')
        download_path = (
            self.base_download_path / repository / dep_type / dependency_name
        )

        # Add customer if present
        if 'customer' in properties:
            download_path = download_path / properties['customer']

        # Add hardware/software variant
        if 'hw_variant' in properties:
            hw_variant = properties['hw_variant']
            if 'sw_variant' in properties:
                download_path = (
                    download_path / f"{hw_variant}_{properties['sw_variant']}"
                )
            else:
                download_path = download_path / hw_variant

        # Add release status or version
        release_status = properties.get('release_status', 'dev')
        if release_status not in ['dev', 'rel']:
            download_path = download_path / release_status
        else:
            download_path = download_path / properties['rb_version']

        return download_path


# Example usage
if __name__ == '__main__':
    # Example configuration
    config = {
        'infineon': {
            'artifactory': 'project',
            'download_rel_dir': '',
            'target_dir': 'dev',
            'needed_for': ['build'],
            'properties': {'rb_version': '2.0.0'},
        },
        'plantuml': {
            'artifactory': 'project',
            'download_rel_dir': 'tools/supplied',
            'target_dir': 'supplied',
            'needed_for': ['doc'],
            'properties': {'rb_version': '1.2024.4'},
        },
        'hexview': {
            'artifactory': 'project',
            'download_rel_dir': 'tools/supplied',
            'target_dir': 'supplied',
            'needed_for': ['build'],
            'properties': {'rb_version': '1.12.05'},
        },
    }

    artifactories = {
        'project': {
            'url': 'https://your-artifactory.com/artifactory',
            'repository': 'your-repo',
        }
    }

    installer = ArtifactoryInstaller(
        artifactories=artifactories, action='build', max_concurrent_downloads=5
    )

    installer.download_dependencies_from_config(config)
