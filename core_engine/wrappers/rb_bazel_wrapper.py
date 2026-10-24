"""RB Bazel wrapper utilities.
"""

import os
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from xc_ce_utils import logger
from xc_ce_utils.bazel.bazel_deploy_binaries import deploy_bazel_binaries

REPO_ROOT = Path(os.getenv('REPO_PATH', Path.cwd()))

#: Set to True after the first emission of the clang-feature warning, so
#: multi-target / multi-build invocations don't spam the log.
_CLANG_WARNING_STATE = {'emitted': False}


def _warn_clang_compile_commands_unsupported(repo_root: Path) -> None:
    """Emit a one-time warning if the project opted into the clang feature.

    The clang feature pins ``_build/compile_commands.json`` for IDE / clangd
    / clang-tidy use. Bazel does not produce a compilation database natively
    — it requires an external aspect (e.g. ``hedron_compile_commands``) — so
    until that integration lands the link will not be refreshed by Bazel
    builds. We detect opt-in by the presence of ``<repo>/.clangd`` which
    ``setup_clang`` generates only when ``CLANG_CONFIG`` is enabled.
    """
    if _CLANG_WARNING_STATE['emitted']:
        return
    if not (repo_root / '.clangd').exists():
        return
    _CLANG_WARNING_STATE['emitted'] = True
    logger.warning(
        'clang feature: compile_commands.json generation for Bazel builds is not '
        'yet implemented. TODO: leverage xc_ce_definitions.bzl + an extractor '
        'aspect (e.g. hedron_compile_commands) to populate '
        '_build/<variant>/<action>/compile_commands.json.'
    )


def _handle_remove_readonly(func, path, _exc):
    """
    Error handler for shutil.rmtree to handle read-only files on Windows and Linux.

    Args:
        func: The function that raised the exception
        path: The path that caused the error
        _exc: The exception information (unused; signature required by shutil.rmtree)
    """
    # Clear the readonly bit and retry
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    func(path)


def _is_ci_isolation_directory(path: Optional[Path]) -> bool:
    """
    Check if a path is a CI isolation directory that's safe to cleanup.

    Args:
        path: Path to check

    Returns:
        True if path is a CI isolation directory in temp folder with bazel_ci_ pattern
    """
    if not path or not path.exists():
        return False

    temp_dir = Path(tempfile.gettempdir())
    path_str = str(path)

    # Must be in temp directory and match CI pattern
    try:
        return path.is_relative_to(temp_dir) and 'bazel_ci_' in path_str
    except (ValueError, OSError):
        return False


@dataclass(frozen=True)
class BazelWrapperOptions:
    """Runtime options for Bazel wrapper operations."""

    output_base: Optional[Path] = None
    bazel_cache: Optional[Path] = None
    deploy_binaries: bool = True
    bin_folder: Optional[Path] = None
    upload_to_remote_cache: Optional[bool] = None
    use_cache: bool = True


class RBBazelWrapper:
    """

    Options = BazelWrapperOptions
    A wrapper class for common Bazel operations in Bosch build environments.

    This class provides a simplified interface for Bazel operations such as building,
    testing, cleaning, and running projects. It supports Bazel's command-line interface
    with proper logging, error reporting, and consistent command execution across
    different environments.

    Key features:
    - Automatic path resolution and directory creation
    - Unified logging of Bazel operations
    - Support for multiple Bazel commands (build, test, clean, run)
    - Configurable build options and flags
    - Automatic binary deployment after successful builds
    - Error handling with detailed logging

    Attributes:
        workspace_dir (Path): Path to the Bazel workspace directory (WORKSPACE file location)
        log_folder (Path): Path to the directory for storing log files
        output_base (Optional[Path]): Custom output base directory for Bazel
        bazel_cache (Optional[Path]): Path to the Bazel cache directory
        deploy_binaries (bool): If True, automatically deploys binaries after build
        bin_folder (str): Destination folder for deployed binaries

    """

    def __init__(
        self,
        log_folder: Path = Path('_logs'),
        workspace_dir: Path = REPO_ROOT,
        options: Optional[BazelWrapperOptions] = None,
    ) -> None:
        """
        Initialize the Bazel wrapper with specified paths and configuration.

        Args:
            log_folder (Path): Directory for storing log files. Defaults to "_logs".
            workspace_dir (Path): Root directory of the Bazel workspace. Defaults to REPO_ROOT.
            options (Optional[BazelWrapperOptions]): Optional wrapper runtime options.

        Side Effects:
            - Creates the log directory if it doesn't exist
            - Resolves all paths to absolute paths
            - Verifies Bazel is available in PATH
            - Detects CI environment if options.upload_to_remote_cache is None
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.log_folder = log_folder.resolve()
        self.log_folder.mkdir(parents=True, exist_ok=True)
        resolved_options = options or BazelWrapperOptions()

        self.output_base = (
            resolved_options.output_base.resolve()
            if resolved_options.output_base
            else None
        )
        self.bazel_cache = (
            resolved_options.bazel_cache.resolve()
            if resolved_options.bazel_cache
            else None
        )
        self.deploy_binaries = resolved_options.deploy_binaries
        self.bin_folder = (
            resolved_options.bin_folder.resolve()
            if resolved_options.bin_folder
            else self.workspace_dir / '_bin'
        )
        self.use_cache = resolved_options.use_cache

        self._configure_ci_and_cache_upload(
            upload_to_remote_cache=resolved_options.upload_to_remote_cache
        )

        # Log cache mode
        cache_mode = (
            'Read/Write (uploads enabled)'
            if self.upload_to_remote_cache
            else 'Read-only'
        )
        logger.debug(f'Remote cache mode: {cache_mode}')

        # Verify Bazel is available
        if not shutil.which('bazel'):
            logger.warning(
                '  Bazel not found in PATH. Please ensure Bazel is installed.'
            )
        else:
            logger.debug(' Bazel found in PATH')

    def _configure_ci_and_cache_upload(
        self, *, upload_to_remote_cache: Optional[bool]
    ) -> None:
        """Resolve CI-specific behavior for cache upload and isolation."""
        if upload_to_remote_cache is None:
            self.is_ci = os.environ.get('GITHUB_ACTIONS', '').lower() == 'true'
            self.upload_to_remote_cache = self.is_ci
            if self.is_ci:
                run_id = os.environ.get('GITHUB_RUN_ID', '')
                job_name = os.environ.get('GITHUB_JOB', '')
                self.ci_job_id = (
                    f'{run_id}_{job_name}' if run_id and job_name else None
                )
                if self.ci_job_id:
                    self.output_base = (
                        Path.home() / f'bazel_ci_{self.ci_job_id}'
                    )
                    logger.info(
                        f' CI detected: Job isolation enabled (ID: {self.ci_job_id})'
                    )
                    logger.debug(f'CI isolation directory: {self.output_base}')
                else:
                    self.ci_job_id = None
                    logger.warning(
                        ' CI detected but job ID unavailable - isolation disabled'
                    )
            else:
                self.ci_job_id = None
            logger.debug(f'Auto-detected CI environment: {self.is_ci}')
        else:
            self.upload_to_remote_cache = upload_to_remote_cache
            self.is_ci = False
            self.ci_job_id = None

    def _cleanup_ci_isolation_directory(self) -> None:
        """
        Clean up CI isolation directory after successful build.

        Only runs when:
        - In GitHub Actions CI environment (self.is_ci = True)
        - output_base is configured and points to a CI isolation directory
        - Directory matches safety checks (in temp dir, has bazel_ci_ pattern)

        Safety: Non-fatal - logs warning if cleanup fails without raising exception.
        """
        # Safety check: only in CI
        if not self.is_ci:
            return

        # Safety check: output_base must be configured
        if not self.output_base:
            return

        # Safety check: must be a CI isolation directory
        if not _is_ci_isolation_directory(self.output_base):
            logger.debug(
                'output_base is not a CI isolation directory - skipping cleanup'
            )
            return

        try:
            logger.progress(' Cleaning up CI isolation directory...')
            logger.debug(f'Removing: {self.output_base}')
            self._remove_directory(self.output_base)
            logger.success(' CI isolation directory cleaned successfully')

        except Exception as e:
            # Non-fatal: build succeeded, cleanup is best-effort
            logger.warning(f' Failed to cleanup CI isolation directory: {e}')
            logger.debug(f'Cleanup error: {type(e).__name__}: {e!s}')

    @staticmethod
    def _remove_directory(path: Path) -> None:
        """Remove a directory tree with cross-version Windows readonly handling."""
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=_handle_remove_readonly)
            return
        shutil.rmtree(path, onerror=_handle_remove_readonly)

    def _get_common_args(self) -> List[str]:
        """
        Get common Bazel arguments that apply to all commands.

        Returns:
            List[str]: Common Bazel arguments for output_base/output_user_root and cache configuration.
        """
        args = []

        # Use --output_user_root for CI isolation (takes precedence over output_base)
        if self.is_ci and self.ci_job_id and self.output_base:
            args.extend(['--output_user_root', str(self.output_base)])
            logger.debug(
                f'Using CI isolation: --output_user_root={self.output_base}'
            )
        elif self.output_base:
            # Use --output_base for local development
            args.extend(['--output_base', str(self.output_base)])

        if self.bazel_cache:
            args.extend(['--disk_cache', str(self.bazel_cache)])

        return args

    def build(
        self,
        target: str = '//...',
        compilation_mode: str = 'opt',
        additional_args: Optional[List[str]] = None,
        *,
        clean: bool = False,
    ) -> None:
        """
        Build Bazel targets.

        This method runs the Bazel build command for specified targets.
        It translates to running 'bazel build <target> --compilation_mode=<mode> [additional args]'.

        Args:
            target (str): The Bazel target(s) to build. Defaults to "//..." (all targets).
                         Examples: "//...", "//path/to:target", "//path/to:all"
            compilation_mode (str): Build compilation mode. Options: "fastbuild", "opt", "dbg".
                                   Defaults to "opt" (optimized).
                                   - fastbuild: Fast compilation, minimal optimization, some debug info
                                   - opt: Optimized build, no debug info (for production)
                                   - dbg: Full debug information, no optimization (for debugging)
            additional_args (Optional[List[str]]): Additional Bazel build flags as strings.
                                                  Examples: ["--verbose_failures", "--keep_going", "--jobs=8"]
            clean (bool): If True, performs a clean build before compiling. Defaults to False.

        Raises:
            RuntimeError: If the build process fails. The original exception is included as the cause.

        Side Effects:
            - Compiles source files and generates build artifacts
            - Logs the build command and its output
            - Creates output files in bazel-out directory
            - Deploys binaries if deploy_binaries is enabled
            - Reports cache statistics after successful build
            - Controls remote cache upload based on CI environment

        Example:
            >>> bazel = RBBazelWrapper()
            >>> bazel.build(target='//src:main', compilation_mode='opt')
            >>> bazel.build(
            ...     target='//...',
            ...     additional_args=[
            ...         '--jobs=8',
            ...         '--remote_cache=https://cache.company.com',
            ...         '--verbose_failures',
            ...     ],
            ...     clean=True,
            ... )
        """
        build_args = self._resolve_build_args(additional_args)
        _warn_clang_compile_commands_unsupported(self.workspace_dir)
        self._prepare_target_bin_folder(target)
        self._maybe_clean_before_build(clean=clean)
        command = self._create_build_command(
            target=target,
            compilation_mode=compilation_mode,
            build_args=build_args,
        )
        self._run_bazel_build(
            command=command,
            target=target,
            compilation_mode=compilation_mode,
        )

    def _resolve_build_args(
        self, additional_args: Optional[List[str]]
    ) -> List[str]:
        """Build command arguments with cache policy applied."""
        args = list(additional_args or [])
        if not self.use_cache:
            args.append('--disk_cache=')
            args.append('--noremote_accept_cached')
            args.append('--noremote_upload_local_results')
            logger.info(' All cache mechanisms disabled via --no-cache option')
            return args

        logger.info(
            f'Using remote cache with upload set to {self.upload_to_remote_cache}'
        )
        args.append(
            f'--remote_upload_local_results={str(self.upload_to_remote_cache).lower()}'
        )
        return args

    def _prepare_target_bin_folder(self, target: str) -> None:
        """Ensure binary deploy directory can be safely refreshed for this target."""
        target_bin_folder = self._get_target_bin_folder(target)
        if target_bin_folder.exists() and not target_bin_folder.is_dir():
            msg = f"Binary deployment folder '{target_bin_folder}' exists and is not a directory."
            raise RuntimeError(msg)

        if not target_bin_folder.exists():
            return

        try:
            self._remove_directory(target_bin_folder)
        except Exception as e:
            logger.warning(f'Failed to remove existing binary folder: {e}')
            raise

        target_bin_folder.mkdir(parents=True, exist_ok=True)

    def _maybe_clean_before_build(self, *, clean: bool) -> None:
        """Run expunge clean when rebuild mode or CI mode requires it."""
        if clean or self.is_ci:
            logger.progress(
                'Performing clean build as requested (rebuild mode)...'
            )
            try:
                self.clean(expunge=True)
            except Exception as e:
                logger.warning(f'Clean operation failed: {e}')
                raise

    def _create_build_command(
        self, target: str, compilation_mode: str, build_args: List[str]
    ) -> List[str]:
        """Create the bazel build command including logging and verbose options."""
        command = [
            'bazel',
            *self._get_common_args(),
            'build',
            target,
            f'--compilation_mode={compilation_mode}',
        ]
        command.extend(build_args)
        self._append_verbose_build_flags(command)
        self._append_build_log_outputs(command, target)
        return command

    @staticmethod
    def _append_verbose_build_flags(command: List[str]) -> None:
        """Append verbose Bazel flags when the verbose env flag is enabled."""
        if os.environ.get('XC_CE_UTILS_VERBOSE', 'false').lower() == 'true':
            command.append('--verbose_failures')
            command.append('--subcommands')

    def _append_build_log_outputs(
        self, command: List[str], target: str
    ) -> None:
        """Append Bazel profile and build-event output paths."""
        if self.log_folder:
            clean_target = (
                target.removeprefix('//').replace('/', '_').replace(':', '_')
            )
            profile_log = (
                self.log_folder / f'bazel_{clean_target}_profile.json.gz'
            ).resolve()
            event_log = (
                self.log_folder / f'bazel_{clean_target}_events.json'
            ).resolve()
            command.append('--profile=' + str(profile_log))
            command.append('--build_event_json_file=' + str(event_log))

    def _run_bazel_build(
        self, command: List[str], target: str, compilation_mode: str
    ) -> None:
        """Execute a Bazel build command and run post-build actions."""
        logger.progress(f"Running Bazel build: {' '.join(command)}")
        try:
            subprocess.run(command, check=True)
        except Exception as e:
            msg = f"Bazel build failed for target '{target}'."
            raise RuntimeError(msg) from e

        logger.success(' Bazel build completed successfully')
        self._report_cache_stats()
        self._maybe_deploy_binaries(target, compilation_mode)
        self._cleanup_ci_isolation_directory()

    def _maybe_deploy_binaries(
        self, target: str, compilation_mode: str
    ) -> None:
        """Deploy build outputs when binary deployment is enabled."""
        if not self.deploy_binaries:
            return

        logger.progress('Deploying binaries...')
        try:
            total_copied = self._deploy_binaries(target, compilation_mode)
        except Exception as e:
            logger.warning(f'Binary deployment failed (build succeeded): {e}')
            return

        if total_copied > 0:
            logger.success(
                f' Deployed {total_copied} binary file(s) to {self.bin_folder}'
            )
            return

        logger.info('No binary files found to deploy')

    def _deploy_binaries(self, target: str, compilation_mode: str) -> int:
        """Run binary deployment and return the number of copied files."""
        total_copied, _files_copied = deploy_bazel_binaries(
            workspace_root=self.workspace_dir,
            targets=[f'bazel-out/*-{compilation_mode}*/bin'],
            dest=self._get_target_bin_folder(target),
            extensions=['.map', '.elf', '.hex', '.bin'],
            verbose=(
                os.environ.get('XC_CE_UTILS_VERBOSE', 'false').lower() == 'true'
            ),
        )
        return total_copied

    def _get_target_bin_folder(self, target: str) -> Path:
        """Return deployment folder for the requested Bazel target."""
        return self.bin_folder / Path(
            target.removeprefix('//').replace(':', '')
        )

    def test(
        self,
        target: str = '//...',
        test_output: str = 'errors',
        additional_args: Optional[List[str]] = None,
    ) -> None:
        """
        Run Bazel tests.

        This method runs tests for specified Bazel test targets.
        It translates to running 'bazel test <target> --test_output=<output> [additional args]'.

        Args:
            target (str): The Bazel test target(s) to run. Defaults to "//..." (all tests).
                         Examples: "//...", "//tests:unit_tests", "//...:all"
            test_output (str): Test output mode. Options: "errors", "all", "streamed", "summary".
                             Defaults to "errors" (only show failing tests).
            additional_args (Optional[List[str]]): Additional Bazel test flags.
                                                  Examples: ["--test_verbose_timeout_warnings"]

        Raises:
            RuntimeError: If the testing process fails. The original exception is included as the cause.

        Side Effects:
            - Executes test binaries
            - Logs the test command and test results
            - Creates test result files in bazel-testlogs directory

        Example:
            >>> bazel = RBBazelWrapper()
            >>> bazel.test(target='//tests:unit_tests', test_output='all')
        """
        additional_args = additional_args or []

        command = [
            'bazel',
            *self._get_common_args(),
            'test',
            target,
            f'--test_output={test_output}',
            *additional_args,
        ]

        logger.progress(f"Running Bazel tests: {' '.join(command)}")

        try:
            subprocess.run(command, check=True)
            logger.success(' Bazel tests completed successfully')
        except Exception as e:
            msg = f"Bazel test failed for target '{target}'."
            raise RuntimeError(msg) from e

    def run(
        self,
        target: str,
        args: Optional[List[str]] = None,
        additional_bazel_args: Optional[List[str]] = None,
    ) -> None:
        """
        Run a Bazel target (typically a binary).

        This method executes a runnable Bazel target.
        It translates to running 'bazel run <target> [bazel_args] -- [target_args]'.

        Args:
            target (str): The Bazel target to run. Must be a runnable target (e.g., binary).
                         Example: "//src:main"
            args (Optional[List[str]]): Arguments to pass to the target binary (after --).
            additional_bazel_args (Optional[List[str]]): Additional Bazel flags (before --).

        Raises:
            RuntimeError: If the run command fails. The original exception is included as the cause.

        Side Effects:
            - Builds the target if necessary
            - Executes the target binary
            - Logs the command and output

        Example:
            >>> bazel = RBBazelWrapper()
            >>> bazel.run(target='//src:main', args=['--config', 'prod'])
        """
        additional_bazel_args = additional_bazel_args or []
        args = args or []

        command = [
            'bazel',
            *self._get_common_args(),
            'run',
            target,
            *additional_bazel_args,
        ]

        if args:
            command.append('--')
            command.extend(args)

        logger.progress(f"Running Bazel target: {' '.join(command)}")

        try:
            subprocess.run(command, check=True)
            logger.success(f" Bazel run completed for '{target}'")
        except Exception as e:
            msg = f"Bazel run failed for target '{target}'."
            raise RuntimeError(msg) from e

    def clean(self, *, expunge: bool = False) -> None:
        """
        Clean Bazel build outputs.

        This method cleans the Bazel output directories. With expunge=False, it performs
        a regular clean. With expunge=True, it removes all build outputs and external
        repositories, requiring a full rebuild.

        Args:
            expunge (bool): If True, performs a full clean (removes everything including
                          external dependencies). If False, performs a regular clean.
                          Defaults to False.

        Raises:
            RuntimeError: If the clean operation fails. The original exception is included as the cause.

        Side Effects:
            - Removes build output directories
            - If expunge=True, also removes external repositories and cache
            - Logs the clean command and output

        Example:
            >>> bazel = RBBazelWrapper()
            >>> bazel.clean()  # Regular clean
            >>> bazel.clean(expunge=True)  # Full clean with expunge
        """
        command = ['bazel', *self._get_common_args(), 'clean']

        if expunge:
            command.append('--expunge')
            logger.progress('Running Bazel clean with expunge (full clean)...')
        else:
            logger.progress('Running Bazel clean...')

        try:
            subprocess.run(command, check=True)
            logger.success(' Bazel clean completed successfully')
        except Exception as e:
            msg = 'Bazel clean failed.'
            raise RuntimeError(msg) from e

    def query(
        self,
        query_expression: str,
        output_format: str = 'label',
        additional_args: Optional[List[str]] = None,
    ) -> None:
        """
        Execute a Bazel query.

        This method runs Bazel query commands to inspect the build graph.
        It translates to running 'bazel query <expression> --output=<format> [args]'.

        Args:
            query_expression (str): The Bazel query expression.
                                   Example: "deps(//src:main)", "//..."
            output_format (str): Output format. Options: "label", "xml", "proto", "graph".
                               Defaults to "label".
            additional_args (Optional[List[str]]): Additional query flags.

        Raises:
            RuntimeError: If the query fails. The original exception is included as the cause.

        Side Effects:
            - Analyzes the build graph
            - Logs the query command and results

        Example:
            >>> bazel = RBBazelWrapper()
            >>> bazel.query('deps(//src:main)')
            >>> bazel.query('//...', output_format='xml')
        """
        additional_args = additional_args or []

        command = [
            'bazel',
            *self._get_common_args(),
            'query',
            query_expression,
            f'--output={output_format}',
            *additional_args,
        ]

        logger.progress(f"Running Bazel query: {' '.join(command)}")

        try:
            subprocess.run(command, check=True)
            logger.success(' Bazel query completed successfully')
        except Exception as e:
            msg = f"Bazel query failed for '{query_expression}'."
            raise RuntimeError(msg) from e

    def info(self, key: Optional[str] = None) -> None:
        """
        Display Bazel workspace information.

        This method retrieves information about the Bazel workspace configuration.
        It translates to running 'bazel info [key]'.

        Args:
            key (Optional[str]): Specific info key to retrieve. If None, shows all info.
                               Examples: "output_base", "execution_root", "workspace"

        Raises:
            RuntimeError: If the info command fails. The original exception is included as the cause.

        Side Effects:
            - Logs the info command and output

        Example:
            >>> bazel = RBBazelWrapper()
            >>> bazel.info()  # Show all info
            >>> bazel.info(key='output_base')  # Show specific key
        """
        command = ['bazel', *self._get_common_args(), 'info']

        if key:
            command.append(key)

        logger.progress(f"Running Bazel info: {' '.join(command)}")
        try:
            result = subprocess.run(command, check=False)
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, command)
        except Exception as e:
            msg = 'Bazel info failed.'
            raise RuntimeError(msg) from e

    def _report_cache_stats(self) -> None:
        """
        Report Bazel cache statistics after a build.

        This method retrieves and displays cache information including:
        - Output base directory
        - Execution root directory
        - Workspace location
        - Output path
        - Disk cache location and size (if configured)
        - Action cache statistics

        Note:
            This is a private method called automatically after successful builds.
            Uses a single 'bazel info' call for efficiency.
        """
        logger.progress(' Gathering cache statistics...')
        try:
            info_dict = self._fetch_bazel_info()
        except Exception as e:
            logger.debug(f'Failed to retrieve cache statistics: {e}')
            return

        if not info_dict:
            return

        self._log_action_cache_stats(info_dict)
        self._log_cache_mode()
        self._log_bazel_info_paths(info_dict)
        self._log_cache_configuration()
        self._log_repository_cache_stats(info_dict)
        logger.success(' Cache statistics retrieved')

    def _fetch_bazel_info(self) -> Dict[str, str]:
        """Fetch and parse `bazel info` output."""
        info_cmd = ['bazel', *self._get_common_args(), 'info']
        result = subprocess.run(
            info_cmd, capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            logger.debug(
                f'Failed to get bazel info: return_code={result.returncode}'
            )
            logger.debug(f'stderr: {result.stderr}')
            return {}

        info_output = result.stdout.strip()
        if not info_output:
            logger.debug('Bazel info returned empty output')
            return {}
        return self._parse_bazel_info_output(info_output)

    @staticmethod
    def _parse_bazel_info_output(info_output: str) -> Dict[str, str]:
        """Parse `bazel info` output into a key/value dictionary."""
        info_dict: Dict[str, str] = {}
        for line in info_output.splitlines():
            if ':' not in line:
                continue
            key, value = line.split(':', 1)
            info_dict[key.strip()] = value.strip()
        return info_dict

    def _log_action_cache_stats(self, info_dict: Dict[str, str]) -> None:
        """Log output-base and action-cache summary details."""
        output_base_value = info_dict.get('output_base')
        if not output_base_value:
            return

        logger.info(f' Output Base: {output_base_value}')
        action_cache_path = Path(output_base_value) / 'action_cache'
        if not action_cache_path.exists():
            return

        stats = self._calculate_directory_stats(
            action_cache_path, 'action cache'
        )
        if not stats:
            return

        file_count, total_size_bytes = stats
        size_mb = total_size_bytes / (1024 * 1024)
        logger.info(
            f'   └─ Action Cache: {file_count} entries, {size_mb:.2f} MB'
        )

    def _log_cache_mode(self) -> None:
        """Log the effective cache mode for the current build."""
        if not self.use_cache:
            cache_mode = 'Disabled (--no-cache)'
        elif self.upload_to_remote_cache:
            cache_mode = 'Read/Write (uploading to remote cache)'
        else:
            cache_mode = 'Read-only (downloading from remote cache)'
        logger.info(f' Remote Cache Mode: {cache_mode}')

    @staticmethod
    def _log_bazel_info_paths(info_dict: Dict[str, str]) -> None:
        """Log selected Bazel info paths when available."""
        for key, label in (
            ('execution_root', ' Execution Root'),
            ('workspace', '  Workspace'),
            ('output_path', ' Output Path'),
        ):
            value = info_dict.get(key)
            if value:
                logger.info(f'{label}: {value}')

    def _log_cache_configuration(self) -> None:
        """Log remote or disk cache configuration and size details."""
        remote_cache_url, disk_cache_path = self._resolve_cache_configuration()
        if remote_cache_url:
            self._log_remote_cache(remote_cache_url)
            return

        if disk_cache_path:
            self._log_disk_cache(disk_cache_path)

    def _resolve_cache_configuration(
        self,
    ) -> Tuple[Optional[str], Optional[Path]]:
        """Resolve configured remote and disk cache locations."""
        if self.bazel_cache:
            return None, Path(self.bazel_cache)
        return self._read_bazelrc_cache()

    def _read_bazelrc_cache(self) -> Tuple[Optional[str], Optional[Path]]:
        """Read `.bazelrc.cache` for remote and disk cache settings."""
        remote_cache_url: Optional[str] = None
        disk_cache_path: Optional[Path] = None
        bazelrc_cache = self.workspace_dir / '.bazelrc.cache'
        if not bazelrc_cache.exists():
            return remote_cache_url, disk_cache_path

        try:
            with bazelrc_cache.open('r', encoding='utf-8') as cache_file:
                for raw_line in cache_file:
                    line = raw_line.strip()
                    if line.startswith('build --remote_cache='):
                        remote_cache_url = line.split('=', 1)[1].strip()
                    elif line.startswith('build --disk_cache='):
                        disk_cache_value = line.split('=', 1)[1].strip()
                        disk_cache_path = Path(disk_cache_value)
        except Exception as e:
            logger.debug(f'Could not read .bazelrc.cache: {e}')

        return remote_cache_url, disk_cache_path

    def _log_remote_cache(self, remote_cache_url: str) -> None:
        """Log remote cache location and auth status."""
        logger.info(f'  Remote Cache: {remote_cache_url}')
        auth_file = self.workspace_dir / '.bazelrc.auth'
        if auth_file.exists() or os.environ.get('BAZEL_CACHE_AUTH'):
            logger.info('   └─ Authentication: Configured ')
            return

        logger.info('   └─ Authentication: Not configured ')
        logger.info(
            '      Set BAZEL_CACHE_USER and BAZEL_CACHE_PASSWORD, then run:'
        )
        logger.info('      .\\config\\bazel\\setup_remote_cache_auth.ps1')

    def _log_disk_cache(self, disk_cache_path: Path) -> None:
        """Log disk cache location and size details."""
        if not disk_cache_path.exists():
            logger.info(f' Disk Cache: {disk_cache_path} (not yet created)')
            return

        logger.info(f' Disk Cache: {disk_cache_path}')
        stats = self._calculate_directory_stats(disk_cache_path, 'disk cache')
        if not stats:
            return

        file_count, total_size_bytes = stats
        logger.info(
            f'   └─ Size: {self._format_size(total_size_bytes)} ({file_count:,} files)'
        )

    def _log_repository_cache_stats(self, info_dict: Dict[str, str]) -> None:
        """Log repository cache size when available."""
        repo_cache_value = info_dict.get('repository_cache')
        if not repo_cache_value:
            return

        repo_cache_path = Path(repo_cache_value)
        if not repo_cache_path.exists():
            return

        stats = self._calculate_directory_stats(
            repo_cache_path, 'repository cache'
        )
        if not stats:
            return

        _file_count, total_size_bytes = stats
        size_mb = total_size_bytes / (1024 * 1024)
        logger.info(f' Repository Cache: {size_mb:.2f} MB')

    @staticmethod
    def _calculate_directory_stats(
        cache_path: Path, label: str
    ) -> Optional[Tuple[int, int]]:
        """Return file count and size for a cache path."""
        try:
            files = [file for file in cache_path.rglob('*') if file.is_file()]
            file_count = len(files)
            total_size = sum(file.stat().st_size for file in files)
        except Exception as e:
            logger.debug(f'Could not read {label}: {e}')
            return None

        return file_count, total_size

    @staticmethod
    def _format_size(total_size_bytes: int) -> str:
        """Format bytes as MB or GB string."""
        size_mb = total_size_bytes / (1024 * 1024)
        size_gb = size_mb / 1024
        if size_gb > 1:
            return f'{size_gb:.2f} GB'
        return f'{size_mb:.2f} MB'
