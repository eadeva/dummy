import json
import os
import re
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from typing import Optional
from zipfile import ZIP_DEFLATED, ZipFile

from xc_ce_utils import logger

REPO_ROOT = Path(os.getenv('REPO_PATH', Path.cwd()))

# Ensure UTF-8 output on Windows to handle emojis and special characters from subprocesses
# This reconfigures sys.stdout/stderr to force UTF-8 encoding even when Windows defaults to cp1252
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, OSError):
        # Fallback for older Python or when reconfigure is not available
        pass


###################################################################################################
# Workaround for long paths inside a zip file - overriding _extract_member function of
# ZipFile to avoid error
###################################################################################################
class ZipfileLongPaths(ZipFile):
    """
    Extension of ZipFile that supports extracting files with long paths on Windows.

    This class overrides the _extract_member method to handle Windows path length limitations.
    """

    def _extract_member(self, member, targetpath, pwd):
        """
        Extract a zip file member with support for long paths.

        Args:
            member: The zip file member to extract
            targetpath (str): The target path to extract to
            pwd: Password for encrypted zip files

        Returns:
            The result of the extraction
        """

        targetpath = self.__winapi_path(targetpath)
        return ZipFile._extract_member(self, member, targetpath, pwd)

    def __winapi_path(self, dos_path: str, encoding: str = None) -> str:
        """
        Convert a DOS path to a Windows API-compatible path for handling long paths.

        Args:
            dos_path (str): Standard DOS path
            encoding (str, optional): Encoding to use. Defaults to None.

        Returns:
            str: Windows API-compatible path with \\\\?\\ prefix
        """

        path = os.path.abspath(dos_path)

        if path.startswith('\\\\'):
            path = '\\\\?\\UNC\\' + path[2:]
        else:
            path = '\\\\?\\' + path

        return path


def run_command(
    command,
    log_file=None,
    realtime_output=True,
    return_success_codes=None,
    cwd=None,
    timeout=None,
    env=None,
    capture_output=False,
):
    """Run a shell command with real-time output and optional log file.

    Output lines are emitted via ``logger.info`` (when *realtime_output* is
    True) or ``logger.debug`` (when False), so they are automatically
    captured by any active ``file_scope`` handler as well as the console.

    A separate *log_file* can still be provided to store the **raw**
    subprocess output without logger formatting — useful for build tools
    that need to parse the log afterwards.

    Args:
        command: Command to run (string or list).
        log_file: Optional path for raw subprocess output.
        realtime_output: If True, log each line at INFO level;
            if False, log at DEBUG level (hidden unless ``-v``).
        return_success_codes: List of acceptable return codes
            (default ``[0]``).
        cwd: Working directory for the subprocess.
        timeout: Maximum wall-clock seconds before the process is
            killed.  ``None`` means no limit.
        env: Environment variables for the subprocess.  ``None``
            inherits the parent process environment.  Pass a custom
            dict to isolate or extend the environment.
        capture_output: If True, return the full captured output as a
            string instead of a status message.
    """
    if return_success_codes is None:
        return_success_codes = [0]

    # Prepare command
    cmd_list = command if isinstance(command, list) else command
    cmd_display = ' '.join(command) if isinstance(command, list) else command
    use_shell = not isinstance(command, list)

    logger.debug(f'Executing: {cmd_display}')

    # Open log file if needed
    log_handle = None
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        log_handle = open(log_file, 'w', encoding='utf-8', errors='replace')

    try:
        # Run process
        process = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding='utf-8',
            errors='replace',
            bufsize=1,
            shell=use_shell,
            cwd=cwd,
            env=env,
        )

        start_time = time.time()
        output_lines = [] if capture_output else None

        # Stream output
        for line in process.stdout:
            line = line.rstrip('\n\r')

            if realtime_output:
                logger.info(line)
            else:
                logger.debug(line)

            if log_handle:
                log_handle.write(line + '\n')

            if output_lines is not None:
                output_lines.append(line)

            if timeout and (time.time() - start_time) > timeout:
                process.kill()
                raise subprocess.TimeoutExpired(cmd_display, timeout)

        return_code = process.wait()

        # Validate return code
        if return_code not in return_success_codes:
            logger.critical(f'Command failed with return code {return_code}')
            raise subprocess.CalledProcessError(return_code, cmd_display)

        if return_code == 0:
            logger.success(f'Command completed with return code {return_code}')
        else:
            logger.info(f'Command finished with accepted return code {return_code}')

        if capture_output:
            return '\n'.join(output_lines)
        return f'Success: {return_code}'

    finally:
        if log_handle:
            log_handle.close()


def is_running_in_ci():
    """
    Check if the script is running in GitHub Actions or Jenkins.

    Returns:
        bool: True if running in GitHub Actions or Jenkins, False otherwise.
    """
    return os.getenv('GITHUB_ACTIONS') == 'true' or os.getenv('JENKINS_HOME') is not None


def zip_folder(
    folder_to_zip,
    zip_file_name,
    target_folder,
    use7z=False,
    zip_extension='zip',
):
    """
    Zips a folder into a zip file with the specified name in the target folder.

    Args:
        folder_to_zip (str or Path): Path to the folder to zip.
        zip_file_name (str): Name of the resulting zip file (without extension).
        target_folder (str or Path): Path to the folder where the zip file will be saved.
        use7z (bool): When True on Windows, use 7z from PATH to create the archive.
        zip_extension (str): Archive extension/format to use in output file name.

    Returns:
        str: Path to the created zip file.
    """
    folder_to_zip = Path(folder_to_zip).resolve()
    target_folder = Path(target_folder).resolve()
    archive_extension = zip_extension.lstrip('.') or 'zip'
    zip_file_path = target_folder / f'{zip_file_name}.{archive_extension}'

    # Ensure the folder to zip exists
    if not folder_to_zip.is_dir():
        raise FileNotFoundError(f'The folder to zip does not exist: {folder_to_zip}')

    # Ensure the target folder exists
    target_folder.mkdir(parents=True, exist_ok=True)

    # Use 7z only when explicitly requested on Windows.
    if os.name == 'nt' and use7z:
        command = [
            '7z',
            'a',
            f'-t{archive_extension}',
            str(zip_file_path),
            '*',
        ]
        try:
            result = subprocess.run(
                command,
                cwd=str(folder_to_zip),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                shell=False,
                check=False,
            )
        except FileNotFoundError as exc:
            raise FileNotFoundError('7z executable not found in PATH') from exc

        if result.returncode != 0:
            output = (result.stdout or '').strip()
            raise RuntimeError(
                f'7z compression failed with exit code {result.returncode}: {output}'
            )

        return str(zip_file_path)

    # Create the zip file
    with ZipFile(zip_file_path, 'w', ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(folder_to_zip):
            for file in files:
                file_path = Path(root) / file
                # Add the file to the zip, preserving the relative path
                zipf.write(file_path, file_path.relative_to(folder_to_zip))

    return str(zip_file_path)


def unzip_7z(file_7z: str, output_dir: str, remove_original_zip: Optional[bool] = False) -> str:
    """
    Extract a 7z archive using the 7z command-line tool.

    Args:
        file_7z (str): Path to the 7z archive file
        output_dir (str): Directory to extract the contents to

    Returns:
        str: Status of the extraction ('failed' if unsuccessful)

    Raises:
        Exception: If an error occurs during extraction
    """

    # Use a direct process invocation and fail on non-zero exit code.
    cmdX = ['7z', 'x', file_7z, f'-o{output_dir}']
    try:
        result = subprocess.run(
            cmdX,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            shell=False,
            check=False,
        )
    except FileNotFoundError as e:
        raise Exception('7z executable not found in PATH') from e

    if result.returncode != 0:
        output = (result.stdout or '').strip()
        raise Exception(f'7z extraction failed with exit code {result.returncode}: {output}')

    logger.debug(f'Unzipping {file_7z} to {output_dir} completed')

    if remove_original_zip:
        try:
            os.remove(file_7z)
            logger.debug(f'Removed original zip file: {file_7z}')
        except Exception as e:
            raise Exception(f'Failed to remove original zip file {file_7z}: {e!s}')

    return 'success'


def unzip_file(file_target_path: str, download_path: str) -> None:
    """
    Extract a compressed file based on its extension.

    Supports .7z, .zip, .gz, and .bz2 file formats.

    Args:
        file_target_path (str): Path to the compressed file
        download_path (str): Directory to extract the contents to

    Raises:
        Exception: If the file doesn't exist, has an unsupported extension,
                  or if an error occurs during extraction
    """

    filename, extension = os.path.splitext(file_target_path)
    if os.path.isfile(file_target_path):
        logger.debug(f'Extracting {extension} file: {filename}')
        logger.debug('This may take a while, grab a coffee...')
        try:
            if extension.lower() in ['.7z', '.zip']:
                unzip_7z(file_target_path, download_path)
            elif extension.lower() in ['.gz', '.bz2']:
                with tarfile.open(file_target_path, 'r') as tar_ref:
                    tar_ref.extractall(download_path)
            else:
                raise Exception(f'[ARTIFACTORY_DOWNLOADER] Unsupported file extension: {extension}')

            logger.info(
                f'[ARTIFACTORY_DOWNLOADER] Extraction of {extension} file: {filename} completed'
            )
        except Exception as e:
            raise Exception(
                f'[ARTIFACTORY_DOWNLOADER] An error occurred while extracting the file: {e!s}'
            )
    else:
        raise Exception(f'[ARTIFACTORY_DOWNLOADER] File {file_target_path} does not exist')


def folder_has_files(folder_path):
    """
    Check if a folder contains any files (recursively).

    Args:
        folder_path (str): Path to the folder.

    Returns:
        bool: True if the folder contains files, False otherwise.
    """
    for _, _, files in os.walk(folder_path):
        if files:  # If the current directory has files
            return True
    return False


def load_environment_variables_from_env_file(env_file):
    if not os.path.exists(env_file):
        return
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            if '=' in line:
                key, value = line.strip().split('=', 1)
                # Expand %VAR% using current environment
                value = expand_win_env_vars(value, os.environ)

                # For PATH, prepend to existing isolated PATH instead of replacing it
                if key.upper() == 'PATH' and key in os.environ:
                    separator = ';' if os.name == 'nt' else ':'
                    os.environ[key] = value + separator + os.environ[key]
                else:
                    os.environ[key] = value


def expand_win_env_vars(value, env):
    # Replace %VAR% with env[VAR] if present
    def replacer(match):
        var = match.group(1)
        return env.get(var, f'%{var}%')

    return re.sub(r'%([^%]+)%', replacer, value)


def export_to_github_env(env_var_name: str, env_var_value: str) -> None:
    """
    Export environment variable to GitHub Actions environment.
    Only exports if GITHUB_ENV is set (running in GitHub Actions).

    Args:
        env_var_name: Name of environment variable
        env_var_value: Value of environment variable
    """
    github_env_file = os.environ.get('GITHUB_ENV')
    if github_env_file:
        try:
            with open(github_env_file, 'a', encoding='utf-8') as f:
                f.write(f'{env_var_name}={env_var_value}\n')
            logger.debug(f'Exported {env_var_name} to GITHUB_ENV')
        except Exception as e:
            logger.debug(f'Failed to export {env_var_name} to GITHUB_ENV: {e}')


def read_io_txt_file_to_dict(filename):
    result = {}
    with open(filename, 'r') as file:
        for line in file:
            if '=' in line:
                key, value = line.strip().split('=', 1)
                result[key] = value

    return result


# Helper function to calculate elapsed time
def get_elapsed_time(start_time):
    """
    Calculate the elapsed time since the given start time.

    Args:
        start_time (float): The start time in seconds.

    Returns:
        str: The elapsed time in minutes, seconds, and milliseconds.
    """
    elapsed = time.time() - start_time
    minutes, seconds = divmod(int(elapsed), 60)
    milliseconds = int((elapsed - int(elapsed)) * 1000)

    elapsed_time = []
    if minutes > 0:
        elapsed_time.append(f'{minutes}m')
    if seconds > 0:
        elapsed_time.append(f'{seconds}s')
    if milliseconds > 0:
        elapsed_time.append(f'{milliseconds}ms')

    return ', '.join(elapsed_time)


def request_post(session, url, data, headers, JSON=True):
    logger.progress(f"Sending request to {url} for {data['action']}")
    # Ensure headers request JSON format
    if 'Accept' not in headers:
        headers['Accept'] = 'application/json'

    json_data = json.dumps(data)
    r = session.post(url, data=json_data, headers=headers)

    if r.ok:
        if not JSON:
            return r.content

        # Check content type of response
        content_type = r.headers.get('Content-Type', '').lower()

        # Log the content type for debugging
        logger.debug(f'Response content type: {content_type}')

        # Handle JSON response
        if 'application/json' in content_type or r.text.strip().startswith('{'):
            try:
                res = json.loads(r.text)
                logger.success(f"Request successfully sent to {url} for {data['action']}")
                logger.debug(f'Response: {r.text}')
                return res
            except json.JSONDecodeError:
                logger.error(f'Failed to parse JSON response: {r.text[:500]}')
                return {
                    'status': '0',
                    'error': 'Invalid JSON response from server',
                }

        # Handle XML response
        elif 'application/xml' in content_type or r.text.strip().startswith('<?xml'):
            logger.warning(f"Server returned XML instead of JSON for {data['action']}")
            # Basic XML parsing
            if '<status>1</status>' in r.text:
                return {
                    'status': '1',
                    'operation': f"Operation {data['action']} completed successfully",
                }
            else:
                return {
                    'status': '0',
                    'error': f'Operation failed with XML response: {r.text[:200]}...',
                }

        # Handle HTML response
        elif (
            'text/html' in content_type
            or r.text.strip().startswith('<!DOCTYPE')
            or r.text.strip().startswith('<html')
        ):
            # Extract title if available for better error message
            title_match = re.search(r'<title>(.*?)</title>', r.text, re.IGNORECASE)
            title = title_match.group(1) if title_match else 'Unknown HTML response'

            # Check for common error messages
            if 'login' in r.text.lower() or 'authentication' in r.text.lower():
                logger.error(f'Authentication failure detected in HTML response: {title}')
                return {
                    'status': '0',
                    'error': f'Authentication error: {title}',
                }
            elif 'error' in r.text.lower() or 'exception' in r.text.lower():
                logger.error('Error page detected in HTML response')
                return {'status': '0', 'error': f'Server error: {title}'}
            elif 'proxy' in r.text.lower():
                logger.error('Proxy interception detected in HTML response')
                return {'status': '0', 'error': f'Proxy error: {title}'}
            else:
                logger.error(f'Unexpected HTML response: {title}')
                return {
                    'status': '0',
                    'error': f'Unexpected HTML response: {title}',
                }

        # Handle any other content type
        else:
            logger.error(f"Unknown response format for {data['action']} ({content_type})")
            return {
                'status': '0',
                'error': f'Unknown response format: {content_type}',
            }
    else:
        logger.error(f'POST request failed {url} ({r.status_code})')

        # Try to extract more detailed error information
        try:
            error_detail = r.text[:500] if r.text else f'HTTP Error {r.status_code}'
            # Check if response looks like JSON
            if r.text.strip().startswith('{'):
                error_json = json.loads(r.text)
                if 'error' in error_json:
                    error_detail = error_json['error']
        except:
            error_detail = f'HTTP Error {r.status_code}'

        return {'status': '0', 'error': f'HTTP request failed: {error_detail}'}


def fossid_result_validation(res, markbuild_as_failure=True):
    logger.debug(f'result {res}')
    msg = res.get('operation', 'None')
    if int(res['status']) == 1:
        msg += res.get('message') if res.get('message', None) else ''
        logger.success(f'{msg}')
    else:
        msg += f" - {res.get('error')}"
        logger.error(f'{msg}') if markbuild_as_failure else logger.debug(f'{msg}')
    return res['status']


def replace_patterns(string_to_parse, replace_variables={}):
    # Function to get the value from environment variables or global_variables
    def get_variable_value(env_var, variables):
        # Check if the environment variable exists
        env_value = os.getenv(env_var)
        if env_var in variables:
            return variables[env_var]
        elif env_value is not None:
            return env_value
        else:
            logger.error(f'Variable <{env_var}> does not exist')

    # Replace patterns like <INPUTS> with environment variable values if they exist
    while '<' in string_to_parse and '>' in string_to_parse:
        start_index = string_to_parse.index('<')
        end_index = string_to_parse.index('>', start_index)
        pattern = string_to_parse[start_index : end_index + 1]
        env_var = pattern[1:-1]  # Remove the angle brackets
        env_value = get_variable_value(env_var, replace_variables)
        string_to_parse = string_to_parse.replace(pattern, env_value)

    return string_to_parse


def replace_variables_in_line(line, variables):
    output_string = line

    # Find all instances of <VARIABLE> in the string
    variables_in_str = re.findall(r'<(.*?)>', output_string)

    # Replace each variable with its value from the dictionary
    for variable in variables_in_str:
        if variable in variables:
            output_string = output_string.replace(f'<{variable}>', variables[variable])
        elif variable in os.environ:
            output_string = output_string.replace(f'<{variable}>', os.getenv(variable))
        else:
            print(f'[VARIABLE REPLACER] Variable {variable} is not available')

    return output_string


def install_python_requirements(requirements_file: str, upgrade: bool = False) -> bool:
    """
    Install Python dependencies from a requirements file.

    This function checks if the specified requirements file exists and uses pip
    to install the dependencies listed in it. It provides detailed logging about
    the installation process and handles errors appropriately.

    Args:
        requirements_file (str): Path to the requirements file to install from.
                                Can be absolute or relative to the repository root.
        upgrade (bool): If True, uses --upgrade flag to update packages to the latest version.
                    Defaults to False.

    Returns:
        bool: True if installation was successful, False otherwise.

    Side Effects:
        - Installs Python packages to the current Python environment
        - Logs progress and any errors that occur during installation

    Example:
        >>> # Modern approach: Use pyproject.toml extras
        >>> # pip install -e .[docascode]
        >>> # Legacy approach (deprecated):
        >>> install_requirements('requirements/doc-requirements.txt')
        INSTALLING PYTHON REQUIREMENTS
        Installing packages from requirements/doc-requirements.txt...
        Successfully installed packages from requirements/doc-requirements.txt
        INSTALLING PYTHON REQUIREMENTS - END
        True
    """
    logger.log_phase_header('INSTALLING PYTHON REQUIREMENTS')

    # Ensure path is absolute
    if not os.path.isabs(requirements_file):
        requirements_file = str(REPO_ROOT / requirements_file)

    # Check if requirements file exists
    if not os.path.exists(requirements_file):
        logger.critical(f'Requirements file not found: {requirements_file}')
        return False

    try:
        import subprocess

        logger.progress(f'Installing packages from {requirements_file}...')

        # Prepare the pip command
        pip_cmd = [
            sys.executable,
            '-m',
            'pip',
            'install',
            '-r',
            requirements_file,
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
            logger.critical(f'Failed to install packages from {requirements_file}')
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
            logger.progress(f'Installation completed in {seconds:.2f} seconds')

        logger.success(f'Successfully installed packages from {requirements_file}')
        logger.log_phase_header('INSTALLING PYTHON REQUIREMENTS - END')
        return True

    except Exception as e:
        logger.critical(f'Error installing packages: {e}')
        return False


# Cross-platform single keypress input (no echo, no Enter required)
def get_single_keypress():
    """
    Returns: str (the pressed key)
    """
    # Check for GUI auto-response environment variable
    if os.getenv('XC_CE_GUI_AUTO_CONFIRM') == 'true':
        return 'y'  # Auto-respond with 'y' for GUI mode

    if os.name == 'nt':
        import msvcrt

        return msvcrt.getch().decode(errors='ignore')
    else:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch


def getpass_with_asterisks(prompt: str = 'Password: ') -> str:
    """Prompt the user for a password, displaying asterisks for each keystroke.

    Gracefully falls back to standard getpass if stdin is not a TTY.
    """
    import sys

    if not sys.stdin.isatty():
        import getpass

        return getpass.getpass(prompt)

    sys.stdout.write(prompt)
    sys.stdout.flush()

    password = []
    while True:
        try:
            ch = get_single_keypress()
        except KeyboardInterrupt:
            sys.stdout.write('\n')
            sys.stdout.flush()
            raise KeyboardInterrupt

        # Check for Enter key (Windows \r, Unix \n)
        if ch in ('\r', '\n'):
            sys.stdout.write('\n')
            sys.stdout.flush()
            break

        # Check for Backspace (Windows \x08, Unix \x7f)
        elif ch in ('\x08', '\x7f'):
            if password:
                password.pop()
                sys.stdout.write('\b \b')
                sys.stdout.flush()

        # Check for Ctrl+C in raw mode on Windows
        elif ch == '\x03':
            sys.stdout.write('\n')
            sys.stdout.flush()
            raise KeyboardInterrupt

        # Standard ASCII characters
        elif len(ch) == 1 and ord(ch) >= 32:
            password.append(ch)
            sys.stdout.write('*')
            sys.stdout.flush()

    return ''.join(password)
