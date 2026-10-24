"""RB CMake wrapper utilities.
"""

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from xc_ce_utils import logger
from xc_ce_utils.clang.clangd_cmake_runner import (
    maybe_configure_clangd_toolchain_from_env,
)
from xc_ce_utils.clang.compile_commands import (
    refresh_compile_commands_symlink,
)
from xc_ce_utils.core_engine.wrappers.cmake_toolchain_utils import (
    prepare_toolchain_argument,
)
from xc_ce_utils.global_modules.aux_helper import run_command

REPO_ROOT = Path(os.getenv('REPO_PATH', Path.cwd()))


@dataclass(frozen=True)
class CMakeWrapperOptions:
    """Runtime options for CMake wrapper operations."""

    build_type: str = 'RelWithDebInfo'
    install_dir: Optional[Path] = Path('_bin')
    ccache_mode: str = 'auto'


class RBCMakeWrapper:
    """
    A wrapper class for common CMake operations in Bosch build environments.

    This class provides a simplified interface for CMake operations such as configuring,
    building, testing, and installing projects. It supports both traditional CMake command
    execution and the newer preset-based workflow. The wrapper handles logging, error
    reporting, and consistent command execution across different environments.

    Key features:
    - Automatic path resolution and directory creation
    - Unified logging of CMake operations
    - Support for CMake presets (configure, build, test)
    - Traditional CMake workflow support (setup, build, test, install)
    - Error handling with detailed logging

    Attributes:
        source_dir (Path): Path to the source directory containing the CMakeLists.txt file
        build_dir (Path): Path to the build directory where build files are generated
        log_folder (Path): Path to the directory for storing log files
        install_dir (Optional[Path]): Path to the installation directory if specified

    """

    def __init__(
        self,
        log_folder: Path = Path('_logs'),
        source_dir: Path = REPO_ROOT,
        build_dir: Path = Path('_builds'),
        options: Optional[CMakeWrapperOptions] = None,
    ) -> None:
        """
        Initialize the CMake wrapper with specified paths and configuration.

        Args:
            log_folder (Path): Directory for storing log files. Defaults to "_logs".
            source_dir (Path): Root directory of the source code. Defaults to REPO_ROOT.
            build_dir (Path): Directory where build files are generated. Defaults to "_builds".
            options (Optional[CMakeWrapperOptions]): Optional wrapper runtime options.

        Side Effects:
            - Creates the log directory if it doesn't exist
            - Resolves all paths to absolute paths
        """
        self.source_dir = Path(os.path.abspath(source_dir))
        self.build_dir = Path(os.path.abspath(build_dir))
        self.log_folder = log_folder.resolve()
        self.log_folder.mkdir(parents=True, exist_ok=True)

        resolved_options = options or CMakeWrapperOptions()
        self.install_dir = (
            resolved_options.install_dir.resolve()
            if resolved_options.install_dir
            else None
        )
        self.build_type = resolved_options.build_type
        self.use_ccache = self._detect_ccache(resolved_options.ccache_mode)

    @staticmethod
    def build_options(
        *,
        build_type: str = 'RelWithDebInfo',
        install_dir: Optional[Path] = Path('_bin'),
        use_ccache: Optional[bool] = None,
    ) -> CMakeWrapperOptions:
        """Build wrapper options with backward-compatible ccache semantics."""
        if use_ccache is None:
            ccache_mode = 'auto'
        else:
            ccache_mode = 'enabled' if use_ccache else 'disabled'

        return CMakeWrapperOptions(
            build_type=build_type,
            install_dir=install_dir,
            ccache_mode=ccache_mode,
        )

    @staticmethod
    def _detect_ccache(ccache_mode: str) -> bool:
        """
        Detect ccache availability and determine if it should be used.

        Args:
            ccache_mode (str): One of: 'enabled', 'disabled', 'auto'.

        Returns:
            bool: True if ccache should be used, False otherwise.
        """

        normalized_mode = str(ccache_mode or 'auto').strip().lower()
        if normalized_mode == 'enabled':
            if not shutil.which('ccache'):
                logger.warning(
                    'ccache requested but not found in PATH. Disabling ccache.'
                )
                return False
            logger.info(' ccache detected and enabled for faster compilation')
            return True

        if normalized_mode == 'disabled':
            logger.debug('ccache explicitly disabled')
            return False

        # Auto-detect ccache
        ccache_available = shutil.which('ccache') is not None
        ccache_env_enabled = os.environ.get('USE_CCACHE', '').lower() in {
            '1',
            'true',
            'yes',
            'on',
        }

        use_ccache_result = ccache_available and ccache_env_enabled

        if use_ccache_result:
            logger.info(' ccache detected and enabled for faster compilation')
        else:
            logger.debug('ccache not available or not enabled')

        return use_ccache_result

    def _get_ccache_cmake_args(self) -> List[str]:
        """
        Get CMake arguments to enable ccache as compiler launcher.

        Returns:
            List[str]: CMake arguments for ccache configuration.
        """
        if not self.use_ccache:
            return []

        ccache_path = shutil.which('ccache')
        if not ccache_path:
            return []

        return [
            f'-DCMAKE_C_COMPILER_LAUNCHER={ccache_path}',
            f'-DCMAKE_CXX_COMPILER_LAUNCHER={ccache_path}',
        ]

    @staticmethod
    def _resolve_clang_refresh_env() -> Dict[str, str]:
        return {
            'variant_alias': str(
                os.environ.get('XC_CE_UTILS_VARIANT_ALIAS', '')
            ).strip(),
            'action_name': str(
                os.environ.get('XC_CE_UTILS_ACTION', '')
            ).strip(),
            'default_variant_alias': str(
                os.environ.get('XC_CE_UTILS_DEFAULT_VARIANT_ALIAS', '')
            ).strip(),
            'repo_root': str(
                os.environ.get('XC_CE_UTILS_REPO_ROOT', str(REPO_ROOT))
            ).strip(),
        }

    @classmethod
    def _refresh_clang_compile_commands(cls) -> None:
        """Refresh the project-level ``_build/compile_commands.json`` link.

        Best-effort hook called at the end of a successful CMake configure.
        Reads variant + default-variant info from environment variables that
        ``action_configuration`` already exports
        (``XC_CE_UTILS_VARIANT_ALIAS``, ``XC_CE_UTILS_DEFAULT_VARIANT_ALIAS``,
        ``XC_CE_UTILS_ACTION``) and delegates to
        :func:`xc_ce_utils.clang.compile_commands.refresh_compile_commands_symlink`,
        which internally honours ``XC_CE_UTILS_PARALLEL_VARIANT_EXECUTION``
        to skip non-default variants during parallel multi-variant builds.

        Never raises -- clang IDE support must not fail the build.
        """
        env_data = cls._resolve_clang_refresh_env()
        if not env_data['variant_alias'] or not env_data['action_name']:
            logger.debug(
                'clang compile_commands refresh skipped: variant/action env not set'
            )
            return

        try:
            refresh_compile_commands_symlink(
                repo_root=Path(env_data['repo_root']),
                variant=env_data['variant_alias'],
                action=env_data['action_name'],
                default_variant=env_data['default_variant_alias'],
            )
        except Exception as exc:
            logger.debug(f'clang compile_commands refresh skipped: {exc}')

    def _maybe_configure_clangd_toolchain(self) -> None:
        """Run the parallel clangd CMake configure (best-effort, post-native).

        Pairs with the native configure in :meth:`setup` -- after the real
        build has produced ``_build/<variant>/build/xc_ce_definitions.cmake``
        we kick off a configure-only CMake invocation under
        ``_build/<variant>/<action>/clangd/`` that uses a generated clang toolchain
        file. The resulting ``compile_commands.json`` overwrites the native
        one (which is preserved as ``compile_commands.native.json``) so the
        existing :func:`refresh_compile_commands_symlink` machinery picks it
        up unchanged.

        Skipped silently when the project does not opt in
        (``config/clang/clang_conf.yml::clangd_toolchain.enabled``) or when
        the project's real compiler is already clang/GCC/MSVC. Never raises
        -- clang IDE support must not fail the build.
        """
        try:
            maybe_configure_clangd_toolchain_from_env(
                source_dir=self.source_dir,
                log_folder=self.log_folder,
            )
        except Exception as exc:
            logger.debug(f'clangd toolchain configure skipped: {exc}')

    def setup(self, cmake_args: Optional[List[str]] = None) -> None:
        """
        Set up the CMake build system by generating build files.

        This method runs the CMake configuration step that generates build files
        for the specified generator (e.g., Ninja, Visual Studio). It translates to
        running 'cmake -S <source_dir> -B <build_dir> [additional args]'.

        Args:
            cmake_args (Optional[List[str]]): Additional arguments to pass to the CMake command.
                                            Examples: ["-DCMAKE_BUILD_TYPE=Release", "-GNinja"]

        Raises:
            RuntimeError: If the CMake configuration process fails. The original exception
                         is included as the cause.

        Side Effects:

            - Creates build files in the build directory
            - Logs the CMake command and its output
            - May create CMake cache and other configuration files

        Example:
            >>> cmake = RBCMakeWrapper()
            >>> cmake.setup(['-DCMAKE_BUILD_TYPE=Release', '-GNinja'])
        """
        cmake_args = cmake_args or []

        # Add ccache arguments if enabled
        ccache_args = self._get_ccache_cmake_args()
        if ccache_args:
            cmake_args = ccache_args + cmake_args
            logger.debug(f'Added ccache arguments: {ccache_args}')

        cmake_args, toolchain_warning = prepare_toolchain_argument(
            cmake_args=cmake_args,
            build_dir=self.build_dir,
            source_dir=self.source_dir,
        )
        if toolchain_warning:
            logger.warning(toolchain_warning)

        command = [
            'cmake',
            '-GNinja',
            '-S',
            str(self.source_dir),
            '-B',
            str(self.build_dir),
            f'-DCMAKE_BUILD_TYPE={self.build_type}',
            *cmake_args,
        ]

        logger.info(f"Running CMake setup: {' '.join(command)}")
        try:
            run_command(command, self.log_folder / 'cmake_setup.log')
        except Exception as e:
            logger.critical(f'Failed to set up CMake: {e}')
            msg = 'CMake setup failed.'
            raise RuntimeError(msg) from e

        # Optionally run the parallel clangd CMake configure (PNG-style):
        # when the project's real compiler is not clang/GCC/MSVC, a second
        # configure-only invocation under _build/<variant>/<action>/clangd/ produces
        # a compile_commands.json that clangd can actually parse. This must
        # run BEFORE the symlink refresh so the refreshed link picks up the
        # promoted (clangd-friendly) database.
        self._maybe_configure_clangd_toolchain()

        # Refresh the project-level _build/compile_commands.json link so
        # clangd / clang-tidy / IDEs see a fresh compilation database for the
        # variant that just configured. Best-effort: never fails the setup.
        # The helper is gated internally by XC_CE_UTILS_PARALLEL_VARIANT_EXECUTION
        # so parallel multi-variant builds only refresh for the default variant.
        self._refresh_clang_compile_commands()

    def build(
        self, target: Optional[str] = None, config: Optional[str] = None
    ) -> None:
        """
        Build the project or a specific target using CMake.

        This method runs the CMake build step for the entire project or a specific target.
        It translates to running 'cmake --build <build_dir> [--target <target>] [--config <config>]'.

        Args:
            target (Optional[str]): The specific target to build (e.g., "all", "clean", or a
                                  specific target defined in the CMakeLists.txt).
                                  If None, builds the default target.
            config (Optional[str]): The build configuration to use (e.g., "Release", "Debug",
                                  "RelWithDebInfo"). Particularly relevant for multi-configuration
                                  generators like Visual Studio. If None, uses the default configuration.

        Raises:
            RuntimeError: If the build process fails. The original exception is included as the cause.

        Side Effects:
            - Compiles source files and generates build artifacts in the build directory
            - Logs the build command and its output
            - Creates object files, libraries, executables as defined in the project

        Example:
            >>> cmake = RBCMakeWrapper()
            >>> cmake.build(target='my_executable', config='Release')
        """
        command = ['cmake', '--build', str(self.build_dir)]
        if target:
            command += ['--target', target]
        if config:
            command += ['--config', config]

        if os.environ['XC_CE_UTILS_VERBOSE'] == 'true':
            command.extend(['--', '-v'])
            if os.environ.get('XC_CE_UTILS_DEVELOPER_MODE'):
                logger.info(
                    'Developer mode enabled: Adding -k 0 to build command to show all errors'
                )
                command.extend(
                    ['-k', '0']
                )  # Don't stop after first error to show all errors

        elif os.environ.get('XC_CE_UTILS_DEVELOPER_MODE'):
            logger.info(
                'Developer mode enabled: Adding -k 0 to build command to show all errors'
            )
            command.extend(
                ['--', '-k', '0']
            )  # Don't stop after first error to show all errors

        logger.progress(f"Running CMake build: {' '.join(command)}")
        try:
            run_command(command, self.log_folder / 'cmake_build.log')
        except Exception as e:
            logger.critical(f'Failed to build the project: {e}')
            msg = 'CMake build failed.'
            raise RuntimeError(msg) from e

    def install(self, config: Optional[str] = None) -> None:
        """
        Install the built project to the specified installation directory.

        This method runs the CMake install step to copy build artifacts to the installation
        directory. It translates to running 'cmake --install <build_dir> [--config <config>]
        --prefix <install_dir>'.

        Args:
            config (Optional[str]): The build configuration to install (e.g., "Release", "Debug").
                                  Relevant for multi-configuration generators. If None, uses
                                  the default configuration.

        Raises:
          ValueError: If the install directory wasn't specified during initialization.
          RuntimeError: If the installation process fails. The original exception is included
          as the cause.

        Side Effects:
          - Copies build artifacts (binaries, libraries, headers, etc.) to the installation directory
          - Logs the install command and its output
          - May create directory structure in the installation path

        Example:
            >>> cmake = RBCMakeWrapper(install_dir=Path('/usr/local'))
            >>> cmake.install(config='Release')
        """
        if not self.install_dir:
            msg = 'Install directory is not specified.'
            raise ValueError(msg)
        command = ['cmake', '--install', str(self.build_dir)]
        if config:
            command += ['--config', config]
        command += ['--prefix', str(self.install_dir)]
        logger.info(f"Running CMake install: {' '.join(command)}")
        try:
            run_command(command)
        except Exception as e:
            logger.critical(f'Failed to install the project: {e}')
            msg = 'CMake install failed.'
            raise RuntimeError(msg) from e

    def test(
        self,
        config: Optional[str] = None,
        output_junit: Optional[Path] = None,
    ) -> None:
        """
        Run tests using CTest.

        This method runs the project's tests using CTest. It translates to running
        'ctest -T --test-dir <build_dir> --output-on-failure [--config <config>]'.

        Args:
            config (Optional[str]): The build configuration to test (e.g., "Release", "Debug").
                                  Relevant for multi-configuration generators. If None, uses
                                  the default configuration.

        Raises:
            RuntimeError: If the testing process fails. The original exception is included as the cause.

        Side Effects:
            - Executes test binaries in the build directory
            - Logs the test command and test results
            - May create test result files in the build directory

        Example:
            >>> cmake = RBCMakeWrapper()
            >>> cmake.test(config='Release')
        """
        command = [
            'ctest',
            '--test-dir',
            str(self.build_dir),
            '--output-on-failure',
        ]
        if config:
            command += ['--config', config]
        if output_junit:
            output_junit.parent.mkdir(parents=True, exist_ok=True)
            command += ['--output-junit', str(output_junit)]
        logger.info(f"Running CMake tests: {' '.join(command)}")
        try:
            run_command(command)
        except Exception as e:
            logger.critical(f'Failed to run tests: {e}')
            msg = 'CTest failed.'
            raise RuntimeError(msg) from e

    def run_preset(
        self,
        preset_name: str,
        action: str = 'configure',
        extra_args: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Run a CMake preset for configure, build, or test operations.

        This method executes a CMake preset defined in CMakePresets.json or CMakeUserPresets.json.
        Presets provide a way to store and reuse common CMake configurations. The method supports
        configure, build, and test actions with additional arguments.

        Args:
            preset_name (str): The name of the preset to use, as defined in CMakePresets.json.
            action (str): The CMake action to perform. Must be one of:
                         - "configure": Generate build files (cmake --preset)
                         - "build": Build the project (cmake --build --preset)
                         - "test": Run tests (ctest --preset)
                         Defaults to "configure".
            extra_args (Optional[Dict[str, Any]]): Additional CMake variables to pass as -D flags.
                                                 Format: {"VAR_NAME": "value"}
                                                 Example: {"CMAKE_BUILD_TYPE": "Release"}

        Raises:
            ValueError: If an unsupported action is specified.
            RuntimeError: If the preset execution fails. The original exception is included as the cause.

        Side Effects:
            - Executes the specified CMake or CTest command
            - Creates a log file in the log directory named cmake_{action}_{preset_name}.log
            - May modify the build environment based on the preset and action

        Example:
            >>> cmake = RBCMakeWrapper()
            >>> cmake.run_preset(
            ...     'default',
            ...     action='configure',
            ...     extra_args={'CMAKE_BUILD_TYPE': 'Release'},
            ... )
            >>> cmake.run_preset('default', action='build')
            >>> cmake.run_preset('default', action='test')
        """
        extra_args = extra_args or {}

        logger.progress(f"Running CMake {action} preset '{preset_name}'.")
        if len(extra_args) > 0:
            logger.info('Build options:')
            cmake_extra_arguments = []
            for arg_name, arg_value in extra_args.items():
                logger.info(f'{arg_name} = {arg_value}')
                cmake_extra_arguments.append(f'-D{arg_name}={arg_value}')

            logger.fill_line_with_character('#')
        else:
            cmake_extra_arguments = []

        if action == 'configure':
            command = ['cmake', '--preset', preset_name, *cmake_extra_arguments]
        elif action == 'build':
            command = ['cmake', '--build', '--preset', preset_name]
            # Add parallel jobs argument for build action
            if 'AVAILABLE_CORES' in os.environ:
                command += ['-j', os.environ['AVAILABLE_CORES']]
            command += cmake_extra_arguments
        elif action == 'test':
            command = ['ctest', '--preset', preset_name, *cmake_extra_arguments]
        else:
            msg = f"Unsupported action: {action}. Use 'configure', 'build', or 'test'."
            raise ValueError(msg)

        try:
            run_command(
                command, self.log_folder / f'cmake_{action}_{preset_name}.log'
            )
        except Exception as e:
            msg = f"CMake preset '{preset_name}' failed for action '{action}'."
            raise RuntimeError(msg) from e
