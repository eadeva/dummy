"""RB Make wrapper utilities.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add the parent directory to the Python path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from xc_ce_utils.global_modules.aux_helper import run_command
from xc_ce_utils.rb_logger.rb_logger import logger

REPO_ROOT = Path(os.getenv('REPO_PATH', Path.cwd()))

#: Set after the first emission of the clang-feature warning to keep the
#: log clean across multi-target invocations.
_CLANG_WARNING_STATE = {'emitted': False}


def _warn_clang_compile_commands_unsupported(repo_root: Path) -> None:
    """Emit a one-time warning if the project opted into the clang feature.

    Make has no native support for ``compile_commands.json``; populating one
    requires wrapping the build with an external tool (``bear``,
    ``compiledb``). Opt-in is detected via the presence of ``<repo>/.clangd``
    which ``setup_clang`` generates only when ``CLANG_CONFIG`` is enabled.
    """
    if _CLANG_WARNING_STATE['emitted']:
        return
    if not (repo_root / '.clangd').exists():
        return
    _CLANG_WARNING_STATE['emitted'] = True
    logger.warning(
        'clang feature: compile_commands.json is not supported for Make builds. '
        '_build/compile_commands.json will not be refreshed. To enable IDE / '
        "clang-tidy support on a Make project, wrap the build with 'bear' or "
        "'compiledb' so a compilation database is emitted."
    )


class RBMakeWrapper:
    """
    A wrapper class for common Make operations in Bosch build environments.

    This class provides a simplified interface for Make operations such as building,
    cleaning, installing, and running specific targets. The wrapper handles logging,
    error reporting, and consistent command execution across different environments.

    Key features:
    - Automatic path resolution and directory creation
    - Unified logging of Make operations
    - Support for Make variables and flags
    - Support for common Make targets (all, clean, install)
    - Error handling with detailed logging

    Attributes:
        source_dir (Path): Path to the source directory containing the Makefile
        build_dir (Path): Path to the build directory where built files are generated
        log_folder (Path): Path to the directory for storing log files
        install_dir (Optional[Path]): Path to the installation directory if specified
        make_path (Optional[str]): Path to the Make executable

    """

    def __init__(
        self,
        make_path: Optional[str] = None,
        log_folder: Path = Path('_logs'),
        source_dir: Path = REPO_ROOT,
        build_dir: Optional[Path] = None,
        install_dir: Optional[Path] = Path('_bin'),
    ) -> None:
        """
        Initialize the Make wrapper with specified paths and configuration.

        Args:
            make_path (Optional[str]): Path to the Make executable. If None, uses Make from PATH.
            log_folder (Path): Directory for storing log files. Defaults to "_logs".
            source_dir (Path): Root directory containing the Makefile. Defaults to REPO_ROOT.
            build_dir (Optional[Path]): Directory where build files are generated.
                                      If None, builds in the source directory.
            install_dir (Optional[Path]): Directory where built artifacts are installed.
                                        Defaults to "_bin". If None, installation is disabled.

        Side Effects:
            - Creates the log directory if it doesn't exist
            - Resolves all paths to absolute paths
        """
        self.source_dir = source_dir.resolve()
        self.build_dir = build_dir.resolve() if build_dir else None
        self.log_folder = log_folder.resolve()
        self.log_folder.mkdir(parents=True, exist_ok=True)
        self.install_dir = install_dir.resolve() if install_dir else None
        self.make_path = (
            make_path or 'make'
        )  # If not specified, use system's make
        self.default_variables: Dict[str, str] = {}

    def run_make(
        self,
        target: Optional[str] = None,
        variables: Optional[Dict[str, str]] = None,
        flags: Optional[List[str]] = None,
        log_file: Optional[Path] = None,
    ) -> None:
        """
        Run make with the specified target, variables, and flags.

        This method provides a general interface to run Make commands with custom
        targets, variables, and flags. It handles proper command construction and error
        handling.

        Args:
            target (Optional[str]): The Make target to build (e.g., "all", "clean").
                                  If None, uses the default target specified in the Makefile.
            variables (Optional[Dict[str, str]]): Make variables to define.
                                                Format: {"VARIABLE": "value"}
                                                Example: {"CC": "gcc", "CFLAGS": "-O2"}
            flags (Optional[List[str]]): Additional flags to pass to Make.
                                       Example: ["-j4", "--no-print-directory"]
            log_file (Optional[Path]): Path to the log file. If None, uses a default path
                                     in the log folder.

        Raises:
            RuntimeError: If the Make process fails. The original exception is included as the cause.

        Side Effects:
            - Executes the Make command in the source or build directory
            - Creates a log file with Make command output
            - Generates build artifacts according to the Makefile rules

        Example:
            >>> make = RBMakeWrapper()
            >>> make.run_make(
            ...     target='all',
            ...     variables={'CC': 'gcc', 'CFLAGS': '-O2'},
            ...     flags=['-j4'],
            ... )
        """
        variables = {**self.default_variables, **(variables or {})}
        flags = flags or []

        # Construct the command
        command = [self.make_path]

        # Add flags
        command.extend(flags)

        # Add variables
        for var_name, var_value in variables.items():
            command.append(f'{var_name}={var_value}')

        # Add target if specified
        if target:
            command.append(target)

        # Determine log file name if not provided
        if not log_file:
            log_file_name = f"make_{target or 'default'}.log"
            log_file = self.log_folder / log_file_name

        logger.info(f"Running Make command: {' '.join(command)}")

        try:
            # Determine the working directory
            working_dir = self.build_dir if self.build_dir else self.source_dir

            # Run the command
            run_command(command, log_file, cwd=str(working_dir))
            logger.info(f'Make command completed successfully. Log: {log_file}')
        except Exception as e:
            logger.critical(f'Make command failed: {e}')
            msg = f"Make failed for target '{target or 'default'}'"
            raise RuntimeError(msg) from e

    def build(
        self,
        target: Optional[str] = 'all',
        parallel_jobs: Optional[int] = None,
        variables: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Build the project using Make.

        This is a convenience method that runs Make with the specified target and options,
        optimized for building the project.

        Args:
            target (Optional[str]): The specific target to build. Defaults to "all".
            parallel_jobs (Optional[int]): Number of parallel jobs to run (-j flag).
                                         If None, doesn't specify a job count.
            variables (Optional[Dict[str, str]]): Make variables to define.
                                                Example: {"CC": "gcc", "CFLAGS": "-O2"}

        Raises:
            RuntimeError: If the build process fails. The original exception is included as the cause.

        Side Effects:
            - Executes the Make command to build the specified target
            - Creates a log file with build output
            - Generates build artifacts according to the Makefile rules

        Example:
            >>> make = RBMakeWrapper()
            >>> make.build(
            ...     target='all', parallel_jobs=4, variables={'CFLAGS': '-O2 -Wall'}
            ... )
        """
        _warn_clang_compile_commands_unsupported(self.source_dir)
        flags = []
        if parallel_jobs:
            flags.append(f'-j{parallel_jobs}')

        log_file = self.log_folder / f'make_build_{target}.log'
        logger.progress(f"Building target '{target}' using Make")

        self.run_make(
            target=target, variables=variables, flags=flags, log_file=log_file
        )
        logger.success(f"Successfully built target '{target}'")

    def clean(self, variables: Optional[Dict[str, str]] = None) -> None:
        """
        Clean the project by running 'make clean'.

        This method removes build artifacts generated during the build process.

        Args:
            variables (Optional[Dict[str, str]]): Make variables to define during cleaning.
                                                Example: {"CLEAN_EXTRA": "yes"}

        Raises:
            RuntimeError: If the clean process fails. The original exception is included as the cause.

        Side Effects:
            - Executes 'make clean'
            - Creates a log file with clean operation output
            - Removes build artifacts according to the Makefile's clean target

        Example:
            >>> make = RBMakeWrapper()
            >>> make.clean()
        """
        log_file = self.log_folder / 'make_clean.log'
        logger.progress('Cleaning build artifacts')

        self.run_make(target='clean', variables=variables, log_file=log_file)
        logger.success('Successfully cleaned build artifacts')

    def install(self, variables: Optional[Dict[str, str]] = None) -> None:
        """
        Install the built project by running 'make install'.

        This method installs the built artifacts to the system or specified installation directory.

        Args:
            variables (Optional[Dict[str, str]]): Make variables to define during installation.
                                                Example: {"DESTDIR": "/custom/install/path"}

        Raises:
            ValueError: If installation is attempted but no installation directory was specified.
            RuntimeError: If the installation process fails. The original exception is included as the cause.

        Side Effects:
            - Executes 'make install'
            - Creates a log file with installation output
            - Copies build artifacts to the installation directory

        Example:
            >>> make = RBMakeWrapper(install_dir=Path('/usr/local'))
            >>> make.install(variables={'INSTALL_STRIP': '1'})
        """
        if not self.install_dir:
            msg = 'Install directory is not specified.'
            raise ValueError(msg)

        variables = variables or {}
        if 'DESTDIR' not in variables and self.install_dir:
            variables['DESTDIR'] = str(self.install_dir)

        log_file = self.log_folder / 'make_install.log'
        logger.progress(f'Installing to {self.install_dir}')

        self.run_make(target='install', variables=variables, log_file=log_file)
        logger.success(f'Successfully installed to {self.install_dir}')

    def run_tests(
        self,
        test_target: str = 'test',
        variables: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Run the project's tests using Make.

        This method runs the test target defined in the Makefile.

        Args:
            test_target (str): The Make target that runs tests. Defaults to "test".
            variables (Optional[Dict[str, str]]): Make variables to define during testing.
                                                Example: {"TEST_VERBOSE": "1"}

        Raises:
            RuntimeError: If the test process fails. The original exception is included as the cause.

        Side Effects:
            - Executes the test target
            - Creates a log file with test output
            - May generate test result files according to the Makefile's test target

        Example:
            >>> make = RBMakeWrapper()
            >>> make.run_tests(
            ...     test_target='check', variables={'TEST_ARGS': '--verbose'}
            ... )
        """
        log_file = self.log_folder / f'make_{test_target}.log'
        logger.progress(f"Running tests with target '{test_target}'")

        self.run_make(
            target=test_target, variables=variables, log_file=log_file
        )
        logger.success('Tests completed successfully')

    def with_variables(self, variables: Dict[str, str]) -> 'RBMakeWrapper':
        """
        Create a new RBMakeWrapper instance with default variables set.

        This method creates a clone of the current wrapper with predefined variables
        that will be used for all subsequent operations. This is useful when you want
        to run multiple Make commands with the same set of variables.

        Args:
            variables (Dict[str, str]): Make variables to use for all subsequent operations.
                                      Example: {"CC": "gcc", "CFLAGS": "-O2 -Wall"}

        Returns:
            RBMakeWrapper: A new wrapper instance with the specified default variables

        Example:
            >>> make = RBMakeWrapper()
            >>> debug_make = make.with_variables({'CFLAGS': '-g -O0', 'DEBUG': '1'})
            >>> debug_make.build()  # Will use the debug flags
        """
        # Create a new instance with the same configuration
        new_wrapper = RBMakeWrapper(
            make_path=self.make_path,
            log_folder=self.log_folder,
            source_dir=self.source_dir,
            build_dir=self.build_dir,
            install_dir=self.install_dir,
        )

        # Store the variables for later use
        new_wrapper.default_variables = dict(variables)

        return new_wrapper

    def create_makefile(
        self,
        template_path: Optional[Path] = None,
        output_path: Optional[Path] = None,
        variables: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Create or customize a Makefile from a template.

        This utility method allows creating a new Makefile from a template,
        with variable substitution. Useful for projects that need dynamic Makefile generation.

        Args:
            template_path (Optional[Path]): Path to the Makefile template. If None, uses a default template.
            output_path (Optional[Path]): Where to write the generated Makefile.
                                        If None, writes to "Makefile" in the source directory.
            variables (Optional[Dict[str, str]]): Variables to substitute in the template.
                                                Format: {"PLACEHOLDER": "value"}

        Raises:
            FileNotFoundError: If the template file doesn't exist
            IOError: If there's an error writing the output file

        Side Effects:
            - Creates or overwrites the output Makefile
            - Logs the Makefile creation process

        Example:
            >>> make = RBMakeWrapper()
            >>> make.create_makefile(
            ...     template_path=Path('template.mk'),
            ...     output_path=Path('Makefile'),
            ...     variables={
            ...         'PROJECT_NAME': 'my_project',
            ...         'SOURCES': 'main.c util.c',
            ...     },
            ... )
        """
        variables = variables or {}
        if not output_path:
            output_path = self.source_dir / 'Makefile'

        if not template_path:
            # Use a simple default template if none is provided
            template_content = """
# Auto-generated Makefile
# Created by RBMakeWrapper

CC = gcc
CFLAGS = -Wall -Wextra -O2
LDFLAGS =

SOURCES = main.c
OBJECTS = $(SOURCES:.c=.o)
TARGET = program

all: $(TARGET)

$(TARGET): $(OBJECTS)
    $(CC) $(LDFLAGS) -o $@ $^

%.o: %.c
    $(CC) $(CFLAGS) -c -o $@ $<

clean:
    rm -f $(OBJECTS) $(TARGET)

install: $(TARGET)
    mkdir -p $(DESTDIR)/_bin
    cp $(TARGET) $(DESTDIR)/_bin/

test:
    @echo "No tests defined"

.PHONY: all clean install test
"""
            logger.info('Using default Makefile template')
        else:
            # Read the template file
            try:
                with open(template_path, 'r') as f:
                    template_content = f.read()
                logger.info(f'Loaded Makefile template from {template_path}')
            except FileNotFoundError:
                logger.critical(f'Template file not found: {template_path}')
                raise

        # Substitute variables
        for var_name, var_value in variables.items():
            template_content = template_content.replace(
                f'@{var_name}@', var_value
            )

        # Write the output file
        try:
            with open(output_path, 'w') as f:
                f.write(template_content)
            logger.success(f'Created Makefile at {output_path}')
        except IOError as e:
            logger.critical(f'Failed to write Makefile: {e}')
            raise
