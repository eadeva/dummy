import getpass
import json
import os
import platform
import re
import socket
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from git import Repo

from xc_ce_utils import logger
from xc_ce_utils.conf_file_loader.conf_file_loader import (
    get_builds_root,
    get_logs_root,
    get_reports_root,
)
from xc_ce_utils.core_engine.domain.exceptions import ConfigurationError
from xc_ce_utils.core_engine.domain.variant_matrix import Variant, VariantMatrix
from xc_ce_utils.global_modules.aux_helper import is_running_in_ci
from xc_ce_utils.repo_dependency_handler.git_helper import GitHelper
from xc_ce_utils.utils.git_source_commit import short_commit, source_commit

# Artifactory upload folder of the current CI run (repository-relative, see Deployer.compute_upload_path)
UPLOAD_PATH_ENV = 'XC_CE_UTILS_ARTIFACTORY_UPLOAD_PATH'


@dataclass
class ActionConfiguration:
    """Type-safe build configuration container."""

    artifact: str
    artifact_version: str
    action: str
    build_type: str
    git_short_commit_hash: str
    git_long_commit_hash: str
    from_phase: str
    to_phase: str
    artifactories: Dict[str, Any]
    additional_params: Dict[str, Any]
    artifact_params: Dict[str, Any]
    action_config: Dict[str, Any]
    conandata: Dict[str, Any] = None
    oss_config: Dict[str, Any] = None
    splunk_config: Dict[str, Any] = None
    reporting_config: Optional[Dict[str, Any]] = None
    report_formats: Optional[List[str]] = None
    interactive_failure_assistance: bool = True
    git_is_dirty: bool = False
    ccache: bool = False
    ccache_dir: Path = None
    no_cache: bool = False
    force_gen: bool = False
    variant: Variant = None
    variant_matrix: VariantMatrix = None
    clean: bool = False
    rebuild: bool = False
    dev_mode: bool = False
    single_file: Optional[str] = None
    repo_root = Path.cwd()
    cmake_wrapper: Optional[Any] = None
    make_wrapper: Optional[Any] = None
    conan_wrapper: Optional[Any] = None
    start_time = datetime.now()

    def __init__(
        self,
        artifact: str,
        version: str,
        action: str,
        from_phase: str,
        to_phase: str,
        additional_params: Dict[str, Any],
        action_config: Dict[str, Any],
        artifactories: Dict[str, Any],
        variant_matrix: VariantMatrix,
        variant: Variant,
        artifact_params: Optional[Dict[str, Any]] = None,
        oss_config: Optional[Dict[str, Any]] = None,
        splunk_config: Optional[Dict[str, Any]] = None,
        reporting_config: Optional[Dict[str, Any]] = None,
        report_formats: Optional[List[str]] = None,
        interactive_failure_assistance: bool = True,
        build_type: Optional[str] = None,
        ccache_active: bool = False,
        ccache_dir: Optional[Path] = None,
        no_cache: bool = False,
        force_gen: bool = False,
        clean: bool = False,
        rebuild: bool = False,
        dev_mode: bool = False,
        single_file: Optional[str] = None,
    ):
        # Set cross-platform environment variables before loading configuration
        self._set_platform_env_variables()

        self._get_git_info()
        self.artifact = artifact
        self.artifact_version = version
        os.environ['RB_VERSION'] = self.artifact_version
        self.action = action
        self.build_type = build_type
        self.ccache = ccache_active
        self.ccache_dir = ccache_dir
        self.no_cache = no_cache
        self.force_gen = force_gen
        self.from_phase = from_phase
        self.to_phase = to_phase
        self.additional_params = additional_params
        self.artifact_params = artifact_params or {}
        self.variant = variant
        self.oss_config = oss_config
        self.splunk_config = splunk_config
        self.reporting_config = reporting_config
        self.report_formats = report_formats
        self.interactive_failure_assistance = interactive_failure_assistance
        self.variant_matrix = variant_matrix
        self.action_config = action_config
        self.artifactories = artifactories
        self.repo_name = Repo(self.repo_root).remotes.origin.url.split('/')[-1].replace('.git', '')
        # Store original action name before any suffix modification (used for config lookups)
        self.original_action = action
        # Rename action with "_sf" suffix for single-file builds so all folder paths and steps use it
        if single_file:
            self.action = f'{action}_sf'
        builds_root = get_builds_root(self.repo_root)
        logs_root = get_logs_root(self.repo_root)
        reports_root = get_reports_root(self.repo_root)
        self.build_folder = builds_root / variant.get_variant_alias() / self.action
        self.bin_folder = self.repo_root / '_bin' / variant.get_variant_alias() / self.action
        if self.force_gen:
            os.environ['XC_CE_UTILS_FORCE_REGENERATION'] = 'true'
        else:
            os.environ['XC_CE_UTILS_FORCE_REGENERATION'] = 'false'

        self.logs_folder = logs_root / variant.get_variant_alias() / self.action
        os.environ['LOGS_FOLDER'] = self.logs_folder.resolve().as_posix()
        self.reports_folder = reports_root / variant.get_variant_alias() / self.action
        os.environ['REPORTS_FOLDER'] = self.reports_folder.resolve().as_posix()
        self.deploy_folder = self.repo_root / '_deploy' / variant.get_variant_alias() / self.action
        os.environ['DEPLOY_FOLDER'] = self.deploy_folder.resolve().as_posix()
        self.clean = clean
        self.rebuild = rebuild
        self.dev_mode = dev_mode
        self.single_file = single_file
        self.conandata = {}

        self.set_conandata()

    def set_conandata(self) -> str:
        """Save conandata to conandata.yml file."""
        if self.action in {'doc', 'sbom'}:
            self.conandata['name'] = f'{self.artifact}_{self.action}'
        else:
            self.conandata['name'] = self.artifact

        self.conandata['action'] = self.action
        self.conandata['version'] = self.artifact_version
        self.conandata['git_long_commit_hash'] = self.git_long_commit_hash
        self.conandata['git_short_commit_hash'] = self.git_short_commit_hash
        self.conandata['git_is_dirty'] = self.git_is_dirty

        conan_options = list(self.variant.get_variant_values().values())
        self.conandata['user'] = conan_options[
            0
        ]  # Assuming first variant level is user (usually customer)

        self.conandata['channel'] = self.get_conan_channel()
        variant_matrix = self.variant_matrix.to_dict()
        self.conandata['options'] = {}
        self.conandata['default_options'] = {}
        variant_matrix_path = self.variant_matrix.variant_matrix_path.split('/')[1:]
        for variant_level in variant_matrix_path:
            self.conandata['options'][variant_level] = []
            self.conandata['options'][variant_level]

        self.conandata['variants'] = {}
        for variant_path, variant in variant_matrix['variants'].items():
            variant_path_split = variant_path.split('/')
            if variant_path_split[0] == self.conandata['user']:
                options_values = variant_path_split[1:]
                for idx, level in enumerate(variant_matrix_path):
                    if idx < len(options_values):
                        value = options_values[idx]
                        if value not in self.conandata['options'][level]:
                            self.conandata['options'][level].append(value)

                        if level not in self.conandata['default_options']:
                            self.conandata['default_options'][level] = value

                new_variant_path = '/'.join(variant_path_split[1:])
                self.conandata['variants'][new_variant_path] = {}
                self.conandata['variants'][new_variant_path]['description'] = variant['description']
                self.conandata['variants'][new_variant_path]['variant_version'] = variant['version']
                self.conandata['variants'][new_variant_path]['options'] = dict(
                    list(variant['variant_values'].items())[1:]
                )
                self.conandata['variants'][new_variant_path]['settings'] = variant['settings']
                self.conandata['variants'][new_variant_path]['settings'] = variant['settings']
                self.conandata['variants'][new_variant_path]['requires'] = variant['requires']
                self.conandata['variants'][new_variant_path]['tool_requires'] = variant[
                    'tool_requires'
                ]
                self.conandata['variants'][new_variant_path]['test_requires'] = variant[
                    'test_requires'
                ]
                self.conandata['variants'][new_variant_path]['build_options'] = variant[
                    'build_options'
                ]
                if 'python_requires' in variant:
                    self.conandata['variants'][new_variant_path]['python_requires'] = variant[
                        'python_requires'
                    ]
                else:
                    self.conandata['variants'][new_variant_path]['python_requires'] = {}

        options_to_remove = []
        for option_name, option_values in self.conandata['options'].items():
            if len(option_values) == 0:
                options_to_remove.append(option_name)

        for option in options_to_remove:
            value = self.conandata['options'].pop(option, None)

    def get_artifactories(self) -> Dict[str, Any]:
        """Get artifactory configuration"""
        return self.artifactories

    def get_logs_folder(self) -> Path:
        """Get logs folder"""
        return self.logs_folder

    def get_reports_folder(self) -> Path:
        """Get logs folder"""
        return self.reports_folder

    def get_deploy_folder(self) -> Path:
        """Get logs folder"""
        return self.deploy_folder

    def get_build_folder(self) -> Path:
        """Get build folder"""
        return self.build_folder

    def get_bin_folder(self) -> Path:
        """Get bin folder"""
        return self.bin_folder

    def get_action_name(self) -> str:
        """Get action name"""
        return self.action

    def get_action_config(self) -> Dict[str, Any]:
        """Get action config"""
        return self.action_config

    def get_variant(self) -> Variant:
        return self.variant

    def get_variant_name(self) -> str:
        """Generate variant name from variant values."""
        if not self.variant:
            msg = 'Variant missing, aborting'
            raise ConfigurationError(msg)

        return '_'.join(self.variant.get_variant_values())

    def get_variant_path(self) -> str:
        """Generate variant path for directories."""
        if not self.variant:
            msg = 'Variant missing, aborting'
            raise ConfigurationError(msg)

        return '_'.join(self.variant.get_variant_values())

    def get_conan_channel(self) -> str:
        """Get the determined Conan channel, computing it if not already set."""
        channel = self.determine_conan_channel()

        self.git_is_dirty = '-dirty' in channel

        return channel

    def determine_conan_channel(self, repo_path: Optional[Path] = None) -> str:
        """
        Determine the appropriate Conan channel based on CI/local environment and branch.

        Args:
            repo_path: Path to the git repository (defaults to repo_root)

        Returns:
            str: The appropriate channel name
        """
        if repo_path is None:
            repo_path = self.repo_root

        channel = self._determine_channel_enhanced(repo_path)

        logger.debug(f'Determined channel for configuration: {channel}')
        return channel

    @staticmethod
    def _set_platform_env_variables():
        """Set unified XC_CE_UTILS_* environment variables for OS-specific values.

        These variables abstract away Windows/Linux differences so that
        configuration files can use a single ``$ENV{XC_CE_UTILS_*}`` name
        regardless of the host OS.
        """
        os.environ['XC_CE_UTILS_MACHINENAME'] = socket.gethostname().lower()
        os.environ['XC_CE_UTILS_USERNAME'] = getpass.getuser().lower()
        os.environ['XC_CE_UTILS_HOME'] = str(Path.home())
        os.environ['XC_CE_UTILS_TMPDIR'] = tempfile.gettempdir()
        os.environ['XC_CE_UTILS_OS'] = platform.system().lower()  # "windows" or "linux"

    def _sanitize_branch_for_channel(self, branch_name: str) -> str:
        """
        Sanitize branch name to be valid for Conan channel.

        Conan channel allows: a-z, A-Z, 0-9, _, -
        Git branch names can contain: /, spaces, and other special chars

        Args:
            branch_name: The branch name to sanitize

        Returns:
            str: Sanitized branch name safe for Conan channel (lowercase)
        """
        # Replace disallowed characters with underscore
        # Keep only alphanumeric, underscore, and hyphen
        sanitized = re.sub(r'[^a-zA-Z0-9_\-]', '_', branch_name)
        # Convert to lowercase for Conan channel
        return sanitized.lower()

    def _truncate_channel_to_limit(self, channel: str, max_length: int = 101) -> str:
        """
        Truncate channel to maximum allowed length by Conan (101 characters).
        Tries to preserve commit hash and author ID by truncating the branch name.

        Args:
            channel: The full channel name
            max_length: Maximum allowed length (default: 101 for Conan)

        Returns:
            str: Truncated channel that fits within the limit
        """
        if len(channel) <= max_length:
            return channel

        # Parse channel format: <branch>-<hash>-<author_id> or <branch>-<hash>-dirty
        parts = channel.rsplit('-', 2)  # Split from right to preserve suffix

        if len(parts) >= 3:
            branch_part = parts[0]
            hash_part = parts[1]
            suffix_part = parts[2]

            # Calculate how much we need to remove
            suffix_length = len(hash_part) + len(suffix_part) + 2  # +2 for the two hyphens
            max_branch_length = max_length - suffix_length

            if max_branch_length > 0:
                truncated_branch = branch_part[:max_branch_length]
                truncated_channel = f'{truncated_branch}-{hash_part}-{suffix_part}'
                logger.warning(
                    f'Channel truncated from {len(channel)} to {len(truncated_channel)} characters: {truncated_channel}'
                )
                return truncated_channel

        # Fallback: just truncate at max_length
        truncated = channel[:max_length]
        logger.warning(f'Channel truncated to {max_length} characters: {truncated}')
        return truncated

    def _determine_channel_enhanced(self, repo_path: Optional[Path] = None) -> str:
        """
        Enhanced channel determination with new strategy.

        CI builds:
        1. Tag pushes: Split tag by '-' and take last element (dev or rel)
        2. PR builds: <branch-name>_<commit-hash>

        Local builds:
        1. development branch: dev (clean) or dev_<commit-hash>-dirty
        2. other branches: <branch-name>_<commit-hash>(-dirty)

        Args:
            repo_path: Path to the git repository (defaults to current working directory)

        Returns:
            str: The appropriate channel name based on new strategy
        """
        try:
            if repo_path is None:
                repo_path = Path.cwd()

            # Initialize GitHelper in read-only mode - we only need to query git metadata,
            # not modify the repo state (no fetch/pull/checkout)
            git_helper = GitHelper(
                repo_path,
                'dummy://url',
                branch=None,
                continue_on_dirty=True,
                read_only=True,
            )
            short_hash = git_helper.get_current_commit_short_hash()

            if is_running_in_ci():
                # CI Environment - determine channel based on GitHub context
                github_event_name = os.getenv('GITHUB_EVENT_NAME', '')
                github_ref = os.getenv('GITHUB_REF', '')

                if github_event_name == 'push' and github_ref.startswith('refs/tags/'):
                    # Tag push - extract channel from tag name
                    # Tag format expected: <anything>-dev or <anything>-rel
                    # Example: v3.1.1-dev, release-2024-rel
                    tag_name = github_ref.replace('refs/tags/', '')
                    tag_parts = tag_name.split('-')

                    if len(tag_parts) >= 2:
                        channel = tag_parts[-1]  # Take last element
                        logger.info(
                            f"CI: Tag push detected, extracted channel '{channel}' from tag '{tag_name}'"
                        )
                        return channel
                    else:
                        # Fallback if tag doesn't follow convention
                        logger.warning(
                            f"CI: Tag '{tag_name}' doesn't follow expected format (<name>-dev|rel), using 'dev'"
                        )
                        return 'dev'
                else:
                    # PR builds - use branch name + commit hash
                    # Get the source branch from PR
                    github_head_ref = os.getenv('GITHUB_HEAD_REF', '')  # Source branch in PR

                    if github_head_ref:
                        # PR build - use source branch name
                        branch_name = github_head_ref
                    else:
                        # Direct push or other event - try to get branch
                        try:
                            branch_name = git_helper.get_current_branch()
                        except RuntimeError:
                            branch_name = 'unknown'

                    sanitized_branch = self._sanitize_branch_for_channel(branch_name)
                    channel = f'{sanitized_branch}-{short_hash}'
                    logger.info(
                        f"CI: PR/push detected, using '{channel}' channel (branch: {branch_name})"
                    )
                    return self._truncate_channel_to_limit(channel)
            else:
                # Local Environment - new strategy
                has_uncommitted = git_helper.has_uncommitted_changes()
                dirty_suffix = '-dirty' if has_uncommitted else ''

                # Get author ID for clean commits
                author_id = ''
                if not has_uncommitted:
                    try:
                        author_id = f'-{git_helper.get_current_commit_author_id()}'
                    except Exception as e:
                        logger.warning(f'Could not get author ID: {e}')
                        author_id = ''

                try:
                    current_branch = git_helper.get_current_branch()
                    logger.debug(f'Local: Current branch is {current_branch}')

                    if current_branch == 'development':
                        # Development branch: dev (clean) or dev-<commit-hash>-dirty
                        if has_uncommitted:
                            channel = f'dev-{short_hash}{dirty_suffix}'
                            logger.info(
                                f"Local: Development branch with changes, using '{channel}' channel"
                            )
                        else:
                            channel = f'dev{author_id}'
                            logger.info(
                                f"Local: Development branch (clean), using '{channel}' channel"
                            )
                        return self._truncate_channel_to_limit(channel)
                    else:
                        # Any other branch: <branch-name>-<commit-hash>(-dirty) or <branch-name>-<commit-hash>-<author-id>
                        sanitized_branch = self._sanitize_branch_for_channel(current_branch)
                        channel = f'{sanitized_branch}-{short_hash}{dirty_suffix}{author_id}'
                        logger.info(f"Local: Branch '{current_branch}', using '{channel}' channel")
                        return self._truncate_channel_to_limit(channel)

                except RuntimeError:
                    # Detached HEAD state - use commit hash with dirty suffix or author ID
                    channel = f'detached-{short_hash}{dirty_suffix}{author_id}'
                    logger.info(f"Local: Detached HEAD, using '{channel}' channel")
                    return self._truncate_channel_to_limit(channel)

        except Exception as e:
            logger.warning(f'Failed to determine enhanced channel from git repository: {e}')
            # Fallback logic
            if is_running_in_ci():
                return 'pr-error'  # Distinguishable error state for CI
            else:
                return 'local-error'  # Distinguishable error state for local

    def _get_current_branch_name(self, repo_path: Optional[Path] = None) -> str:
        """Get current branch name for CI and local environments.

        CI behavior:
        - PR events: source branch (GITHUB_HEAD_REF)
        - Push events: branch name from refs/heads/*
        """
        if repo_path is None:
            repo_path = self.repo_root

        if is_running_in_ci():
            github_event_name = os.getenv('GITHUB_EVENT_NAME', '')
            github_head_ref = os.getenv('GITHUB_HEAD_REF', '')
            github_ref = os.getenv('GITHUB_REF', '')
            github_ref_name = os.getenv('GITHUB_REF_NAME', '')

            if github_event_name.startswith('pull_request') and github_head_ref:
                return github_head_ref

            if github_ref.startswith('refs/heads/'):
                return github_ref.replace('refs/heads/', '')

            if github_ref_name and not github_ref.startswith('refs/tags/'):
                return github_ref_name

            jenkins_branch = os.getenv('BRANCH_NAME', '')
            if jenkins_branch:
                return jenkins_branch

        try:
            git_helper = GitHelper(
                repo_path,
                'dummy://url',
                branch=None,
                continue_on_dirty=True,
                read_only=True,
            )
            return git_helper.get_current_branch()
        except RuntimeError:
            return 'unknown'

    def write_git_managed_version_file(self):
        """Write this action's own _builds/<variant>/<action>/version.json.

        Only active when RB_VERSIONING is git-managed (see
        xc_ce_utils.utils.git_version_resolver). Recomputes independently per
        action/phase (fresh git describe/status each time) rather than
        reusing the value computed once at CLI startup, so each action's
        build folder carries its own self-contained version record.
        """
        if os.environ.get('XC_CE_UTILS_RB_VERSIONING_MODE') not in {
            'git-managed',
            'variant-git-managed',
        }:
            return

        from xc_ce_utils.utils.git_version_resolver import (
            DEFAULT_TAG_PATTERN,
            RB_VERSION_PATTERN_ENV,
            resolve_git_managed_version,
        )

        tag_pattern = (
            getattr(self.variant, 'version_pattern', None)
            or os.environ.get(RB_VERSION_PATTERN_ENV)
            or DEFAULT_TAG_PATTERN
        )
        version_components = resolve_git_managed_version(self.repo_root, tag_pattern)
        self.build_folder.mkdir(parents=True, exist_ok=True)
        version_file = self.build_folder / 'version.json'
        with open(version_file, 'w', encoding='utf-8') as fh:
            json.dump(version_components, fh, indent=4)
            fh.write('\n')
        logger.info(f'Wrote git-managed version file: {version_file}')

    def _get_git_info(self):
        """Get all git information with error handling"""
        try:
            repo_path = Path(os.environ['REPO_PATH'])
            self.git_long_commit_hash = source_commit(repo_path)
            self.git_short_commit_hash = short_commit(repo_path, self.git_long_commit_hash)

            # Debug logging
            logger.info(' BuildConfiguration git hash calculation:')
            logger.info(f'   Short hash: {self.git_short_commit_hash}')
            logger.info(f'   Long hash: {self.git_long_commit_hash}')
            logger.info(f'   Repo path: {os.environ["REPO_PATH"]}')

            os.environ['GIT_SHORT_COMMIT_HASH'] = self.git_short_commit_hash
            os.environ['GIT_LONG_COMMIT_HASH'] = self.git_long_commit_hash
            os.environ['GIT_COMMIT_IS_DIRTY'] = str(self.git_is_dirty)

        except Exception as e:
            msg = f'Could not get git info: {e}'
            raise Exception(msg) from e

    def _load_conan_pkg_config(self) -> Dict[str, Any]:
        """Load conan package configuration from conan_pkg_config.yml files in conanfile directories."""
        conan_configs = {}

        # Find all conanfile paths in action config
        if 'PHASES' in self.action_config:
            for phase_name, phase_config in self.action_config['PHASES'].items():
                if 'conanfile_path' in phase_config:
                    conanfile_path = Path(self.repo_root) / phase_config['conanfile_path']
                    conan_config_path = conanfile_path.parent / 'conan_pkg_config.yml'

                    if conan_config_path.exists():
                        try:
                            with open(conan_config_path, 'r') as f:
                                config_data = yaml.safe_load(f) or {}

                            # Use package name from config as key, or phase name as fallback
                            config_key = config_data.get('name', phase_name)
                            conan_configs[config_key] = config_data

                            logger.debug(
                                f'Loaded conan package config for {config_key} from {conan_config_path}'
                            )
                        except Exception as e:
                            logger.warning(
                                f'Error loading conan package config from {conan_config_path}: {e}'
                            )

        return conan_configs

    def dump_configuration(self, yaml_format: bool = True) -> str:
        """Dump configuration to file with conan package configuration included."""
        from dataclasses import asdict

        def serialize(obj):
            if isinstance(obj, Path):
                return str(obj)
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, Variant):
                return obj.get_variant_path()
            if isinstance(obj, VariantMatrix):
                return obj.to_dict()
            msg = f'Type {type(obj)} not serializable'
            raise TypeError(msg)

        # Prepare data with conan package config
        config_data = asdict(self)

        if yaml_format:
            dump_file = self.get_build_folder() / 'build_configuration.yml'
            dump_file.parent.mkdir(parents=True, exist_ok=True)
            with open(dump_file, 'w') as f:
                # Convert to JSON first to handle serialization, then to YAML
                json_data = json.loads(json.dumps(config_data, default=serialize))
                yaml.dump(json_data, f, default_flow_style=False, sort_keys=False)
        else:
            dump_file = self.get_build_folder() / 'configuration.json'
            dump_file.parent.mkdir(parents=True, exist_ok=True)
            with open(dump_file, 'w') as f:
                json.dump(config_data, f, default=serialize, indent=4)

        logger.success(f'Build configuration saved to {dump_file}')
        return str(dump_file)

    def dump_conandata_yaml(self) -> str:
        """Dump conandata to file with conan package configuration."""
        conandata_file = self.get_build_folder() / 'conandata.yml'
        conandata_file.parent.mkdir(parents=True, exist_ok=True)

        with conandata_file.open('w') as f:
            yaml.dump(self.conandata, f, default_flow_style=False, sort_keys=False)

        logger.success(f'Conandata saved to {conandata_file}')
        return str(conandata_file)

    def _export_artifactory_upload_path(self) -> None:
        """Export this CI run's Artifactory upload folder (UPLOAD_PATH_ENV).

        Also appended to GITHUB_ENV so that later steps of the workflow job can use it.
        """
        if not is_running_in_ci():
            return
        from xc_ce_utils.core_engine.adapters.deployment.artifactory_deployer import (  # noqa: PLC0415
            Deployer,
        )

        try:
            upload_path = Deployer.compute_upload_path(
                self.repo_root, self.artifact_version, self.repo_name
            )
        except Exception as exc:
            logger.warning(f'Could not resolve the Artifactory upload path: {exc}')
            return

        os.environ[UPLOAD_PATH_ENV] = upload_path
        github_env = os.environ.get('GITHUB_ENV')
        if github_env:
            with Path(github_env).open('a', encoding='utf-8') as handle:
                handle.write(f'{UPLOAD_PATH_ENV}={upload_path}\n')

    def dump_env_variables(self) -> None:
        """Log current environment variables to a file."""
        env_file = self.get_build_folder() / 'xc-ce-utils.env'
        env_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.variant:
            msg = 'Variant missing, aborting'
            raise ConfigurationError(msg)

        def write_to_file_and_log_env_variable(
            variable_name, variable_value, file, set_env_variable=True
        ):
            current_env_variable_str = f'{variable_name}={variable_value}'
            file.write(f'{current_env_variable_str}\n')
            logger.debug(f'   - {current_env_variable_str}')

            if set_env_variable:
                os.environ[variable_name] = str(variable_value)

        def log_env_variable(variable_name, file):
            variable_value = os.environ.get(variable_name, None)
            if not variable_value:
                msg = f"Environment variable '{variable_name}' is not set"
                raise ConfigurationError(msg)

            current_env_variable_str = f'{variable_name}={variable_value}'
            file.write(f'{current_env_variable_str}\n')
            logger.debug(f'   - {current_env_variable_str}')

        logger.debug('Builder env variables:')
        current_branch_name = self._get_current_branch_name()
        # Ensure clang locators are populated for projects that opted into
        # the clang feature, even when the clang setup phase was hash-gated
        # this run (so its CHOCO_CLANG / CHOCO_CLANG_BIN exports never
        # happened). Best-effort: silently skips for non-clang projects.
        try:
            from xc_ce_utils.clang.config_layer import (
                ensure_clang_env_populated,
            )

            ensure_clang_env_populated(self.repo_root)
        except Exception as exc:  # pragma: no cover - never block the dump
            logger.debug(f'ensure_clang_env_populated skipped: {exc}')

        # Write environment variables in the current process and in a file
        with env_file.open('w') as f:
            write_to_file_and_log_env_variable(
                'VENV_PYTHON_PATH', str(Path(sys.executable).parent), f, False
            )
            log_env_variable('PROJECT_NAME', f)
            log_env_variable('XC_CE_UTILS_VERSION', f)
            log_env_variable('XC_CE_UTILS_MACHINENAME', f)
            log_env_variable('XC_CE_UTILS_USERNAME', f)
            log_env_variable('XC_CE_UTILS_HOME', f)
            log_env_variable('XC_CE_UTILS_TMPDIR', f)
            log_env_variable('XC_CE_UTILS_OS', f)
            log_env_variable('XC_CE_UTILS_BUILDS_DIR', f)
            log_env_variable('XC_CE_UTILS_LOGS_DIR', f)
            log_env_variable('XC_CE_UTILS_REPORTS_DIR', f)

            write_to_file_and_log_env_variable('XC_CE_UTILS_REPO_NAME', self.repo_name, f)
            write_to_file_and_log_env_variable('XC_CE_UTILS_REPO_ROOT', self.repo_root, f)
            write_to_file_and_log_env_variable('XC_CE_UTILS_BRANCH_NAME', current_branch_name, f)
            write_to_file_and_log_env_variable('XC_CE_UTILS_ARTIFACT', self.artifact, f)
            write_to_file_and_log_env_variable('XC_CE_UTILS_USER', self.conandata['user'], f)
            write_to_file_and_log_env_variable('XC_CE_UTILS_ACTION', self.action, f)
            write_to_file_and_log_env_variable(
                'XC_CE_UTILS_RELEASE_STATUS', self.conandata['channel'], f
            )
            write_to_file_and_log_env_variable(
                'GIT_SHORT_COMMIT_HASH',
                os.environ['GIT_SHORT_COMMIT_HASH'],
                f,
                False,
            )
            write_to_file_and_log_env_variable(
                'GIT_LONG_COMMIT_HASH',
                os.environ['GIT_LONG_COMMIT_HASH'],
                f,
                False,
            )
            write_to_file_and_log_env_variable(
                'GIT_COMMIT_IS_DIRTY',
                os.environ['GIT_COMMIT_IS_DIRTY'],
                f,
                False,
            )
            # Only set when RB_VERSIONING is git-managed (see git_version_resolver.py) -
            # absent entirely in static version.json mode; the upload path only in CI.
            self._export_artifactory_upload_path()
            for optional_var in (
                'RB_COMMITS_AHEAD',
                'RB_COMMIT_HASH',
                'RB_FULL_VERSION_TAG',
                'RB_VERSION_PATTERN',
                UPLOAD_PATH_ENV,
            ):
                optional_value = os.environ.get(optional_var)
                if optional_value is not None:
                    write_to_file_and_log_env_variable(optional_var, optional_value, f, False)
            write_to_file_and_log_env_variable(
                'XC_CE_UTILS_VARIANT', self.variant.get_variant_path(), f
            )
            write_to_file_and_log_env_variable(
                'XC_CE_UTILS_VARIANT_ALIAS', self.variant.get_variant_alias(), f
            )

            write_to_file_and_log_env_variable(
                'XC_CE_UTILS_CALIBRATION_VARIANTS',
                ','.join(self.variant.get_calibration_variants()),
                f,
            )

            if self.variant_matrix is not None:
                write_to_file_and_log_env_variable(
                    'XC_CE_UTILS_DEFAULT_VARIANT_ALIAS',
                    self.variant_matrix.get_default_variant_alias(),
                    f,
                )
            # Already using underscore for filesystem paths
            write_to_file_and_log_env_variable(
                'XC_CE_UTILS_FORCE_REGENERATION',
                os.environ.get('XC_CE_UTILS_FORCE_REGENERATION', 'false'),
                f,
                False,
            )

            for (
                variant_level,
                variant_value,
            ) in self.variant.variant_values.items():
                write_to_file_and_log_env_variable(
                    variant_level.replace('-', '_').upper(), variant_value, f
                )
                write_to_file_and_log_env_variable(
                    f'BO_{variant_value.replace("-", "_").upper()}', 1, f
                )

            for (
                build_option_name,
                build_option_value,
            ) in self.variant.build_options.items():
                write_to_file_and_log_env_variable(
                    f'BO_{build_option_name.replace("-", "_").upper()}',
                    build_option_value,
                    f,
                )

            for setting, value in self.variant.get_settings().items():
                write_to_file_and_log_env_variable(f'SETTING_{setting.upper()}', value, f)

            # Optional toolchain locators exported by EnvironmentSetup
            # phases that run before the action context exists. Only emit
            # when the variable was actually populated upstream so projects
            # that don't use the feature don't get spurious empty lines.
            choco_clang = os.environ.get('CHOCO_CLANG')
            if choco_clang:
                write_to_file_and_log_env_variable('CHOCO_CLANG', choco_clang, f, False)
            choco_clang_bin = os.environ.get('CHOCO_CLANG_BIN')
            if choco_clang_bin:
                write_to_file_and_log_env_variable('CHOCO_CLANG_BIN', choco_clang_bin, f, False)

            # Developer mode and single-file build env variables
            if self.dev_mode:
                write_to_file_and_log_env_variable(
                    'XC_CE_UTILS_DEVELOPER_MODE',
                    os.environ.get('XC_CE_UTILS_DEVELOPER_MODE', 'false'),
                    f,
                    False,
                )
            if self.single_file:
                write_to_file_and_log_env_variable(
                    'XC_CE_UTILS_SINGLE_FILE_BUILD',
                    os.environ.get('XC_CE_UTILS_SINGLE_FILE_BUILD', 'false'),
                    f,
                    False,
                )
                write_to_file_and_log_env_variable(
                    'XC_CE_UTILS_FULL_PATH_SINGLE_FILE',
                    os.environ.get('XC_CE_UTILS_FULL_PATH_SINGLE_FILE', ''),
                    f,
                    False,
                )

        logger.success(f'Environment variables logged to {env_file}')

    def dump_full_environment(self) -> None:
        """Dump a snapshot of all current environment variables to full_environment.env."""
        full_env_file = self.get_build_folder() / 'full_environment.env'
        full_env_file.parent.mkdir(parents=True, exist_ok=True)
        with full_env_file.open('w') as f:
            for key in sorted(os.environ.keys()):
                f.write(f'{key}={os.environ[key]}\n')
        logger.debug(f'Full environment snapshot saved to {full_env_file}')
