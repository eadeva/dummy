"""
Script Runner Utility

This module provides functionality to run external scripts with parameters.
It handles different script types and formats parameters appropriately for
command-line execution.

Example:
    runner = ScriptRunner()
    result = runner.run_script("path/to/script.py", {"param1": "value1", "flag": True})
"""

import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from xc_ce_utils import logger
from xc_ce_utils.global_modules.aux_helper import run_command


class RBScriptRunner:
    """
    A class for running external scripts with parameters.

    This class handles the execution of scripts, converting dictionary parameters
    into command-line arguments, and capturing output and errors.

    .. uml:: _diagrams/script_runner.puml
        :align: center

    Attributes:
        logger (logging.Logger): Logger for capturing execution information.
        working_dir (Path): The working directory for script execution.
        capture_output (bool): Whether to capture the script's output.
        timeout (Optional[int]): Maximum execution time in seconds, None for no limit.

    """

    def __init__(
        self,
        working_dir: Optional[Union[str, Path]] = None,
        logs_dir: Optional[Union[str, Path]] = None,
        timeout: Optional[int] = None,
    ) -> None:
        """
        Initialize the ScriptRunner with execution options.

        Args:
            working_dir: Directory to run the script in. Defaults to current directory.
            logs_dir: Directory for log files.
            timeout: Maximum execution time in seconds. Default is None (no timeout).
        """
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()
        self.logs_dir = logs_dir
        if logs_dir:
            self.log_file = (
                Path(logs_dir) / 'script.log'
                if logs_dir
                else self.working_dir / 'script.log'
            )
        else:
            self.log_file = None
        self.timeout = timeout

        if not self.working_dir.exists():
            logger.warning(
                f'Working directory {self.working_dir} does not exist. Creating it.'
            )
            self.working_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _format_parameters(
        parameters: Union[Dict[str, Any], List[Any], None],
    ) -> List[str]:
        """
        Convert parameters to command-line arguments.

        Args:
            parameters: Dictionary or list representation.
                - String values become "--name value"
                - Boolean True becomes "--name"
                - Boolean False is omitted
                - None values are omitted
                - Lists become multiple arguments

        Returns:
            List of formatted command-line arguments.
        """
        args: List[str] = []

        if parameters is None:
            return args

        if isinstance(parameters, list):
            return [str(item) for item in parameters if item is not None]

        if not isinstance(parameters, dict):
            msg = 'parameters must be a dict or list'
            raise TypeError(msg)

        for name, value in parameters.items():
            # Convert parameter name to command-line format
            param_name = f'{name}' if len(name) > 1 else f'-{name}'

            # Handle different value types
            if value is None:
                continue
            elif isinstance(value, bool):
                if value:
                    args.append(param_name)
            elif isinstance(value, list):
                for item in value:
                    args.append(param_name)
                    args.append(str(item))
            else:
                args.append(param_name)
                args.append(str(value))

        return args

    @staticmethod
    def _resolve_script_path(script_path: Union[str, Path]) -> Path:
        resolved = Path(script_path)
        if resolved.exists():
            return resolved
        msg = f'Script not found: {resolved}'
        raise FileNotFoundError(msg)

    @staticmethod
    def _python_launcher(script_path: Path) -> List[str]:
        if not getattr(sys, 'frozen', False):
            return [sys.executable]

        logger.debug(
            f'Running script {script_path} as subprocess via '
            f'frozen executable _exec subcommand'
        )
        return [sys.executable, '_exec']

    @staticmethod
    def _powershell_launcher() -> List[str]:
        if sys.platform == 'win32':
            return ['powershell.exe', '-ExecutionPolicy', 'Bypass', '-File']
        return ['pwsh', '-File']

    @staticmethod
    def _find_windows_bash() -> str:
        bash_locations = [
            r'C:\Program Files\Git\bin\bash.exe',
            r'C:\Program Files (x86)\Git\bin\bash.exe',
            'bash',
        ]
        for bash_path in bash_locations:
            try:
                result = subprocess.run(
                    [bash_path, '--version'],
                    capture_output=True,
                    timeout=2,
                    check=False,
                )
                if result.returncode == 0:
                    return bash_path
            except (FileNotFoundError, subprocess.SubprocessError):
                continue

        msg = (
            'Bash not found. To run .sh scripts on Windows, install Git Bash or WSL.\n'
            f"Searched locations: {', '.join(bash_locations)}"
        )
        raise FileNotFoundError(msg)

    def _shell_launcher(self) -> List[str]:
        if sys.platform == 'win32':
            return [self._find_windows_bash()]
        return ['bash']

    def _build_launcher_command(self, script_path: Path) -> List[str]:
        suffix = script_path.suffix.lower()
        if suffix in {'.py', '.pyw'}:
            return self._python_launcher(script_path)
        if suffix == '.ps1':
            return self._powershell_launcher()
        if suffix == '.sh':
            return self._shell_launcher()
        return []

    @staticmethod
    def _script_argument(script_path: Path) -> str:
        if script_path.suffix.lower() == '.sh':
            return script_path.as_posix()
        return str(script_path)

    def _update_log_file(self, script_path: Path) -> None:
        if not self.log_file:
            return
        self.log_file = Path(
            str(self.log_file).replace('script.log', f'{script_path.stem}.log')
        )

    def _execute_script_command(
        self,
        command: List[str],
        return_success_codes: Sequence[int],
    ) -> None:
        try:
            run_command(
                command,
                self.log_file,
                return_success_codes=list(return_success_codes),
            )
        except subprocess.TimeoutExpired as err:
            msg = f'Script execution timed out after {self.timeout} seconds'
            raise Exception(msg) from err
        except Exception as err:
            msg = f'Error executing script: {err}'
            raise Exception(msg) from err

    def run_script(
        self,
        script_path: Union[str, Path],
        return_success_codes: Optional[Sequence[int]] = None,
        parameters: Union[Dict[str, Any], List[Any], None] = None,
    ) -> Tuple[int, str, str]:
        """
        Run a script with the given parameters.

        Args:
            script_path: Path to the script to execute.
            parameters: Dictionary of parameters to pass to the script.
                See _format_parameters for details on parameter formatting.
            env_vars: Environment variables to set for the script execution.
            log_file: Path to write script output to.

        Returns:
            Tuple containing (return_code, stdout, stderr).

        Raises:
            FileNotFoundError: If the script doesn't exist.
            subprocess.TimeoutExpired: If the script execution times out.
            subprocess.SubprocessError: For other subprocess-related errors.
        """
        script_path_obj = self._resolve_script_path(script_path)
        command = self._build_launcher_command(script_path_obj)
        command.append(self._script_argument(script_path_obj))

        if parameters:
            command.extend(self._format_parameters(parameters))

        self._update_log_file(script_path_obj)
        success_codes = return_success_codes or [0]
        self._execute_script_command(command, success_codes)


if __name__ == '__main__':
    # Example usage
    runner = RBScriptRunner()

    # Example 1: Run a Python script with parameters
    try:
        return_code, stdout, stderr = runner.run_script(
            'example.py', {'verbose': True, 'count': 5, 'output': 'results.txt'}
        )
        print(f'Return code: {return_code}')
        print(f'Output: {stdout}')
    except FileNotFoundError:
        print('Example script not found')
