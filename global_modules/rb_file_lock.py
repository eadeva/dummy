import errno
import logging
import os
import platform
import random
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from xc_ce_utils import logger


class FileLock:
    """
    A file-based locking mechanism to prevent race conditions between processes.

    This class provides a robust locking system for coordinating access to shared
    resources (like tool installations) between multiple concurrent processes.
    It handles stale locks, timeouts, and proper cleanup.

    Features:

    - Atomic lock acquisition
    - Stale lock detection and cleanup
    - Timeout support with exponential backoff
    - Context manager support for automatic lock release

    Example::

        # Using as a context manager (recommended)
        with FileLock('artifactory_download') as lock:
            # Download or install tools here
            pass
    """

    def __init__(
        self,
        lock_name: str,
        lock_dir: Optional[Union[str, Path]] = None,
        timeout: float = 600.0,
        check_interval: float = 0.5,
        stale_age: float = 3600.0,
    ) -> None:
        """
        Initialize a new file lock.

        Args:
            lock_name: A unique name for the lock
            lock_dir: Directory to store lock files (defaults to ~/.build_locks)
            timeout: Maximum time to wait for lock acquisition in seconds
            check_interval: Time between lock acquisition attempts in seconds
            stale_age: Time in seconds after which a lock is considered stale

        Raises:
            ValueError: If lock_name is empty or invalid
        """
        if not lock_name or not isinstance(lock_name, str):
            raise ValueError('Lock name must be a non-empty string')

        self.lock_name = lock_name
        self.timeout = timeout
        self.check_interval = check_interval
        self.stale_age = stale_age

        # Set up lock directory
        if lock_dir is None:
            self.lock_dir = Path.home() / '.build_locks'
        else:
            self.lock_dir = Path(lock_dir)

        # Create lock directory if it doesn't exist
        self.lock_dir.mkdir(parents=True, exist_ok=True)

        # Define lock file path
        self.lock_file = self.lock_dir / f'{self.lock_name}.lock'
        self.is_locked = False

    def acquire(self, blocking: bool = True) -> bool:
        """
        Acquire the lock.

        Args:
            blocking: If True, wait until lock is acquired or timeout.
                     If False, return immediately if lock cannot be acquired.

        Returns:
            bool: True if lock was acquired, False otherwise

        Raises:
            TimeoutError: If blocking is True and lock could not be acquired within timeout
            OSError: If there's an issue with file operations
        """
        if self.is_locked:
            return True

        start_time = time.time()
        attempts = 0

        while True:
            try:
                # Attempt to create the lock file exclusively
                self._create_lock_file()
                self.is_locked = True
                logger.debug(f'Lock acquired: {self.lock_name}')
                return True
            except FileExistsError:
                if self._handle_existing_lock():
                    # Lock was stale and has been removed, try again
                    continue

                if not blocking:
                    return False

                # Calculate elapsed time
                elapsed = time.time() - start_time
                if elapsed >= self.timeout:
                    raise TimeoutError(
                        f"Could not acquire lock '{self.lock_name}' within {self.timeout} seconds"
                    )

                # Calculate backoff time with jitter to prevent thundering herd
                attempts += 1
                max_interval = min(
                    self.check_interval * (2 ** min(attempts, 6)), 10
                )  # Cap at 10 seconds
                wait_time = max_interval * (0.5 + random.random())

                logger.warning(
                    f"Waiting {wait_time:.2f}s for lock '{self.lock_name}' (attempt {attempts})"
                )
                time.sleep(wait_time)
            except OSError as e:
                if e.errno == errno.EACCES:
                    logger.error(
                        f'Permission denied when creating lock file: {self.lock_file}'
                    )
                raise

    def release(self) -> None:
        if not self.is_locked:
            return

        try:
            # Verify we own the lock before releasing
            if self.lock_file.exists():
                try:
                    # Use a separate scope for reading to ensure handles are closed
                    with open(self.lock_file, 'r') as f:
                        content = f.read().strip().split('\n')[0]

                    # Only delete if this process owns the lock
                    if content == str(os.getpid()):
                        # On Windows, delay slightly to allow handles to fully close
                        if platform.system() == 'Windows':
                            time.sleep(0.05)
                        self._safe_remove_lock_file()
                except Exception as e:
                    logger.warning(f'Error checking lock ownership: {e}')
                    # Try to remove anyway
                    self._safe_remove_lock_file()

            self.is_locked = False
        except OSError as e:
            logger.error(f"Error releasing lock '{self.lock_name}': {e}")

    def _create_lock_file(self) -> None:
        """
        Create the lock file atomically with this process's PID.

        Raises:
            FileExistsError: If the lock file already exists
            OSError: If there's an issue with file operations
        """
        # Use 'x' mode for exclusive creation (atomic operation)
        with open(self.lock_file, 'x') as f:
            f.write(f'{os.getpid()}\n{time.time()}')

    def _handle_existing_lock(self) -> bool:
        """
        Check if an existing lock is stale and remove it if necessary.

        Returns:
            bool: True if the lock was stale and has been removed, False otherwise
        """
        try:
            # Check lock file age and content
            if not self.lock_file.exists():
                return True

            # Check if lock file is too old
            stats = self.lock_file.stat()
            if (time.time() - stats.st_mtime) > self.stale_age:
                logger.warning(
                    f'Removing stale lock: {self.lock_name} (age > {self.stale_age}s)'
                )
                try:
                    self._safe_remove_lock_file()
                    return True
                except OSError:
                    logger.warning(
                        'Could not remove stale lock file due to access restrictions'
                    )
                    return False

            # Read PID from lock file
            try:
                with open(self.lock_file, 'r') as f:
                    content = f.read().strip().split('\n')

                if not content:
                    # Empty lock file, consider it stale
                    self._safe_remove_lock_file()
                    return True

                try:
                    pid = int(content[0])

                    # Check if process is still running
                    if not self._is_process_running(pid):
                        logger.warning(
                            f'Removing stale lock: {self.lock_name} (process {pid} not running)'
                        )
                        self._safe_remove_lock_file()
                        return True
                except (ValueError, IndexError):
                    # Invalid content, consider it stale
                    logger.warning(
                        f'Removing invalid lock file: {self.lock_name}'
                    )
                    self._safe_remove_lock_file()
                    return True
            except OSError as e:
                # File might be temporarily locked for reading
                logger.debug(f'Could not read lock file: {e}')
                return False

        except OSError as e:
            logger.error(f"Error checking lock file '{self.lock_name}': {e}")
            # Don't consider it stale if we can't check
            return False

        return False

    def _safe_remove_lock_file(self) -> None:
        """
        Safely remove the lock file with Windows-specific handling.
        """
        for attempt in range(5):  # More retries
            try:
                # For Windows, use the win32 API for more reliable file operations
                if platform.system() == 'Windows':
                    try:
                        # First, try to use Windows-specific deletion
                        import pywintypes
                        import win32con
                        import win32file

                        try:
                            # Force close any open handles to the file
                            win32file.SetFileAttributes(
                                str(self.lock_file),
                                win32con.FILE_ATTRIBUTE_NORMAL,
                            )
                            # Delete the file
                            win32file.DeleteFile(str(self.lock_file))
                            return  # Success!
                        except pywintypes.error:
                            # Fall back to standard method if the Win32 API fails
                            pass
                    except ImportError:
                        # pywin32 not available, use standard approach
                        pass

                # Standard approach - will work on Unix and as fallback on Windows
                if self.lock_file.exists():
                    self.lock_file.unlink(missing_ok=True)
                return  # Success!

            except OSError as e:
                logger.debug(
                    f'Attempt {attempt+1} to remove lock file failed: {e}'
                )
                if attempt < 4:  # Don't sleep on the last attempt
                    time.sleep(0.5 * (attempt + 1))  # Longer backoff

        # If we got here, we couldn't remove the file after all attempts
        logger.warning(
            f'Failed to remove lock file {self.lock_file} after multiple attempts'
        )

    def _is_process_running(self, pid: int) -> bool:
        """
        Check if a process with the given PID is running.

        Args:
            pid: Process ID to check

        Returns:
            bool: True if the process is running, False otherwise
        """
        if pid <= 0:
            return False

        # Windows-specific approach
        if platform.system() == 'Windows':
            import ctypes

            kernel32 = ctypes.windll.kernel32
            SYNCHRONIZE = 0x00100000
            process = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if process != 0:
                kernel32.CloseHandle(process)
                return True
            return False

        # Unix-based systems
        else:
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                return False

    def __enter__(self) -> 'FileLock':
        """Context manager entry point."""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit point."""
        self.release()

    def __del__(self) -> None:
        """Destructor to ensure lock is released."""
        if self.is_locked:
            try:
                self.release()
            except Exception:
                pass


class BuildDependencyLock:
    """
    A specialized locking system for build dependencies and tool installation.

    This class provides a convenient interface for locking operations related to
    downloading and installing build dependencies and Python packages.

    Example::

        # For tool installation
        with BuildDependencyLock.for_tool('hexview', '1.2.3'):
            # Install hexview tool here
            pass
    """

    @staticmethod
    @contextmanager
    def for_tool(tool_name: str, tool_version: str) -> None:
        """
        Create a lock for installing a specific tool.

        Args:
            tool_name: Name of the tool being installed
            tool_version: Version of the tool being installed

        Yields:
            None: This is a context manager that doesn't yield a value

        Raises:
            TimeoutError: If lock cannot be acquired within timeout
            OSError: If there's an issue with file operations
        """
        lock_name = f'tool_{tool_name}_{tool_version}'
        with FileLock(lock_name) as lock:
            yield

    @staticmethod
    @contextmanager
    def for_requirements(requirements_file: Union[str, Path]) -> None:
        """
        Create a lock for installing Python requirements from a file.

        Args:
            requirements_file: Path to the requirements file

        Yields:
            None: This is a context manager that doesn't yield a value

        Raises:
            TimeoutError: If lock cannot be acquired within timeout
            OSError: If there's an issue with file operations
        """
        # Create a hash of the requirements file path to use as lock name
        req_path = Path(requirements_file).resolve()
        lock_name = f'req_{req_path.stem}_{hash(str(req_path)) % 10000}'
        with FileLock(lock_name) as lock:
            yield

    @staticmethod
    def is_tool_installed(tool_name: str, tool_version: str) -> bool:
        """
        Check if a tool is already installed by looking for a marker file.

        Args:
            tool_name: Name of the tool
            tool_version: Version of the tool

        Returns:
            bool: True if the tool is installed, False otherwise
        """
        marker_dir = Path.home() / '.build_tools'
        marker_file = marker_dir / f'{tool_name}_{tool_version}.installed'
        return marker_file.exists()

    @staticmethod
    def mark_tool_installed(tool_name: str, tool_version: str) -> None:
        """
        Mark a tool as installed by creating a marker file.

        Args:
            tool_name: Name of the tool
            tool_version: Version of the tool

        Raises:
            OSError: If there's an issue creating the marker file
        """
        marker_dir = Path.home() / '.build_tools'
        marker_dir.mkdir(parents=True, exist_ok=True)
        marker_file = marker_dir / f'{tool_name}_{tool_version}.installed'
        marker_file.touch()


# Example functions to use with the locking mechanism


def download_artifactory_dependency(
    artifactory: str,
    repository: str,
    dependency_name: str,
    dependency_details: Dict[str, Any],
    download_path: Path,
) -> Tuple[str, str, bool]:
    """
    Download a dependency from Artifactory with file locking to prevent race conditions.

    Args:
        artifactory: The URL of the Artifactory server
        repository: The name of the repository
        dependency_name: The name of the dependency to download
        dependency_details: Details about the dependency
        download_path: Path to download the dependency to

    Returns:
        Tuple[str, str, bool]: Tuple of (dependency_name, path, was_downloaded)
    """
    rb_properties = dependency_details.get('properties', {})
    if not rb_properties:
        raise Exception(
            f"At least 'rb_version' must be specified for artifactory dependency {dependency_name}"
        )

    version = rb_properties.get('rb_version')
    if not version:
        raise Exception(
            f"'rb_version' must be specified for artifactory dependency {dependency_name}"
        )

    download_path = download_path / version

    # Check if already installed first (without a lock)
    if download_path.exists():
        return dependency_name, str(download_path), False

    # Use the locking mechanism to prevent race conditions
    with BuildDependencyLock.for_tool(dependency_name, version):
        # Check again after acquiring the lock (another process might have installed it)
        if download_path.exists():
            return dependency_name, str(download_path), False

        try:
            # Your existing download code here
            from xc_ce_utils.artifactory_utils.artifactory_downloader import (
                ArtifactoryDownloader,
            )

            download_rel_path = f'{dependency_name}/**/*'
            last_one = True
            unzip = True
            delete = True

            # Create download directory
            download_path.mkdir(parents=True, exist_ok=True)

            # Download artifact
            downloader = ArtifactoryDownloader(artifactory, repository)

            # Find artifacts matching the pattern and properties
            artifacts = downloader.get_artifacts_by_properties_fast(
                download_rel_path, rb_properties or {}
            )

            # If only_last is True, get only the most recent artifact
            if last_one and artifacts:
                artifacts = [
                    max(artifacts, key=lambda x: x.get('modified', ''))
                ]

            if not artifacts:
                raise Exception(
                    f'Dependency {dependency_name} version {version} not found'
                )

            # Download the artifacts
            artifact_specs = [
                {
                    'name': artifact['name'],
                    'rel_path': artifact['path'] + '/' + artifact['name'],
                    'download_subdir': '',
                }
                for artifact in artifacts
            ]
            results = downloader.download_artifacts_batch(
                artifact_specs, download_path, unzip=unzip
            )

            if not results or not any(
                was_downloaded for _, _, was_downloaded in results
            ):
                raise Exception(
                    f'Dependency {dependency_name} version {version} not found'
                )

            # Mark as installed in environment variable
            os.environ[f'BUILD_DEP_{dependency_name.upper()}_VERSION'] = version

            # Mark as successfully installed
            BuildDependencyLock.mark_tool_installed(dependency_name, version)

            return dependency_name, str(download_path), True

        except Exception as e:
            # Clean up partial downloads on error
            if download_path.exists():
                try:
                    shutil.rmtree(download_path)
                except Exception as cleanup_error:
                    logging.error(
                        f'Failed to clean up {download_path}: {cleanup_error}'
                    )
            raise Exception(f'Failed to download {dependency_name}: {e}') from e


def install_requirements(
    requirements_file: Union[str, Path], upgrade: bool = False
) -> bool:
    """
    Install Python dependencies from a requirements file with file locking to prevent race conditions.

    Args:
        requirements_file: Path to the requirements file
        upgrade: If True, uses --upgrade flag to update packages

    Returns:
        bool: True if installation was successful, False otherwise
    """
    from xc_ce_utils import logger

    logger.log_phase_header('INSTALLING PYTHON REQUIREMENTS')

    # Ensure path is absolute
    req_path = Path(requirements_file)
    if not req_path.is_absolute():
        # Assuming REPO_ROOT is defined in your global scope
        req_path = Path(os.getenv('REPO_PATH', Path.cwd())) / req_path

    # Check if requirements file exists
    if not req_path.exists():
        logger.critical(f'Requirements file not found: {req_path}')
        return False

    # Use file locking to prevent race conditions
    with BuildDependencyLock.for_requirements(req_path):
        try:
            import subprocess

            logger.progress(f'Installing packages from {req_path}...')

            # Prepare the pip command
            pip_cmd = [
                sys.executable,
                '-m',
                'pip',
                'install',
                '-r',
                str(req_path),
            ]
            if upgrade:
                pip_cmd.append('--upgrade')

            # Run pip install
            start_time = time.time()
            result = subprocess.run(
                pip_cmd,
                capture_output=True,
                text=True,
                check=False,  # Don't raise exception on non-zero return code
            )

            if result.returncode != 0:
                logger.critical(f'Failed to install packages from {req_path}')
                logger.critical(f'Error: {result.stderr}')
                return False

            # Calculate and log elapsed time
            elapsed_time = time.time() - start_time
            minutes, seconds = divmod(elapsed_time, 60)

            if minutes > 0:
                logger.progress(
                    f'Installation completed in {int(minutes)} minutes and {seconds:.2f} seconds'
                )
            else:
                logger.progress(
                    f'Installation completed in {seconds:.2f} seconds'
                )

            logger.success(f'Successfully installed packages from {req_path}')
            logger.log_phase_header('INSTALLING PYTHON REQUIREMENTS - END')
            return True

        except Exception as e:
            logger.critical(f'Error installing packages: {e}')
            return False
