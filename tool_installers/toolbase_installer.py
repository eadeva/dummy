# Impor# Import necessary libraries
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from xc_ce_utils import logger

# Constants
XML_FILE = 'toolbase_tools.xml'
ENV_VAR = 'TB_HOMEDIR'


def parse_args():
    parser = argparse.ArgumentParser(
        description='Toolbase setup script',
        epilog='This scripts installs tools defined in toolsets from an xml configuration file.',
    )
    parser.add_argument(
        '--config', '-c', dest='tools_config', help='Config json file', type=str
    )
    parser.add_argument(
        '--tools_env',
        '-e',
        dest='env_file',
        help='Path to the generated .env file',
        type=str,
    )
    parser.add_argument(
        '--append_tools_env',
        '-a',
        dest='append_to_env_file',
        help='Appends the new tools to the .env, if false, .env will be rewritten',
        type=bool,
    )
    return parser.parse_args()


def add_tool_for_installation(env, tool_name, tool_version):
    if os.path.exists(
        f"{os.environ['TB_HOMEDIR']}" + '/' + tool_name + '/' + tool_version
    ):
        logger.info(f'{tool_name}/{tool_version} already installed')
        return False
    else:
        # If the tool is not installed, print a message and run a system command to install the tool
        logger.info(
            f'[TB_INSTALLER] {tool_name}/{tool_version} missing - Adding to tool installation'
        )
        subprocess.run(
            f'tbexcmd -useEnv:{env} -command EnableTool {tool_name}/{tool_version}',
            check=False,
        )
        return True


def run_toolbase_update():
    return subprocess.run(['TBUpdate', '-e'], check=False).returncode


def install_tools(tools_config, tb_env, env_file, append_to_env_file=False):
    logger.log_phase_header('TOOLBASE INSTALLER')
    start_time = time.time()

    TOOLBASE_HOMEDIR = os.getenv(ENV_VAR)
    if not TOOLBASE_HOMEDIR:
        logger.critical(
            f'[TB_INSTALLER] {ENV_VAR} environment variable is not set.'
        )
        sys.exit(1)

    enabled_tools = []
    if Path(env_file).exists() and append_to_env_file == False:
        os.remove(env_file)

    if append_to_env_file:
        file_open_mode = 'a'
    else:
        file_open_mode = 'w'

    with open(env_file, file_open_mode) as myfile:
        python_exe = Path(sys.executable).parent
        if file_open_mode == 'w':
            myfile.write(f'VENV_PYTHON_PATH={python_exe}\n')

    try:
        if isinstance(tools_config, str):
            # tools_config is a Path object
            filename = Path(tools_config)

            if not Path(filename).exists():
                logger.critical(
                    f'[TB_INSTALLER] The file {tools_config} does not exist.'
                )
                sys.exit(1)

            with open(filename, 'r') as f:
                data = json.load(f)
        elif isinstance(tools_config, Path):
            if not Path(tools_config).exists():
                logger.critical(
                    f'[TB_INSTALLER] The file {tools_config} does not exist.'
                )
                sys.exit(1)

            with open(tools_config, 'r') as f:
                data = json.load(f)
        elif isinstance(tools_config, dict):
            data = tools_config
        else:
            raise Exception(
                'Toolbase config is neither a Path, str or dictionary'
            )

        # Extract tools for the specified environment
        if tb_env in data:
            tools_data = data[tb_env]
        else:
            tools_data = data

        for tool_name, tool in tools_data.items():
            tool_version = tool.get('version')

            # If the tool is already installed, print a message
            if (Path(TOOLBASE_HOMEDIR) / tool_name / tool_version).exists():
                logger.info(
                    f'[TB_INSTALLER] {tool_name}/{tool_version} already installed'
                )
            else:
                # If the tool is not installed, print a message and run a system command to install the tool
                result = subprocess.run(
                    f'tbexcmd -useEnv:{tb_env} -command EnableTool {tool_name}/{tool_version}',
                    shell=True,
                    check=False,
                )
                if result.returncode != 0:
                    logger.critical(
                        f'[TB_INSTALLER] Failed to enable {tool_name}/{tool_version} '
                        f'(exit code {result.returncode}).'
                    )
                    sys.exit(1)
                enabled_tools.append(f'{tool_name}/{tool_version}')

            # If the tool has an environment variable, add it to the toolbase.env file
            env_variable = tool_name
            if 'alias' in tool:
                env_variable = tool.get('alias')

            env_variable = f'TOOLBASE_{env_variable.upper()}'

            env_variable_value = (
                Path(TOOLBASE_HOMEDIR) / tool_name / tool_version
            )
            if 'subfolder' in tool:
                env_variable_value = env_variable_value / tool.get('subfolder')

            try:
                with open(env_file, 'a') as myfile:
                    myfile.write(f'{env_variable}={env_variable_value}\n')

                os.environ[env_variable] = str(env_variable_value)

                # Export to GitHub Actions environment if running in CI
                from xc_ce_utils.global_modules.aux_helper import (
                    export_to_github_env,
                )

                export_to_github_env(env_variable, str(env_variable_value))

                # Adding env variable value to PATH if it is not already present
                current_path = os.environ.get('PATH', '')
                new_path = str(env_variable_value)
                if new_path not in current_path:
                    os.environ['PATH'] = f'{new_path};{current_path}'
                    logger.debug(f'[TB_INSTALLER] Added {new_path} to PATH')
                    # Export PATH to GITHUB_ENV as well
                    export_to_github_env('PATH', os.environ['PATH'])
                else:
                    logger.debug(f'[TB_INSTALLER] {new_path} already in PATH')

                # Special case: Python installations also need the Scripts subdirectory
                # in PATH so that pip, uv, and other entry-point executables are found.
                if tool_name.lower() == 'python':
                    scripts_path = str(Path(env_variable_value) / 'Scripts')
                    current_path = os.environ.get('PATH', '')
                    if scripts_path not in current_path:
                        os.environ['PATH'] = f'{scripts_path};{current_path}'
                        logger.debug(
                            f'[TB_INSTALLER] Added {scripts_path} to PATH (Python Scripts)'
                        )
                        export_to_github_env('PATH', os.environ['PATH'])
                    else:
                        logger.debug(
                            f'[TB_INSTALLER] {scripts_path} already in PATH'
                        )

            except Exception as e:
                logger.critical(
                    f'[TB_INSTALLER] Failed to write to .env file. Exception: str{e}'
                )
                sys.exit(1)

    except FileNotFoundError:
        logger.critical(f'[TB_INSTALLER] The file {filename} does not exist.')
    except json.JSONDecodeError:
        logger.critical(
            f'[TB_INSTALLER] The file {filename} is not a valid JSON file.'
        )

    # Run Toolbase update only when at least one tool was actually enabled.
    if enabled_tools:
        logger.info(
            "[TB_INSTALLER] Running TBUpdate because new tools were enabled: "
            f"{', '.join(enabled_tools)}"
        )
        if subprocess.run(['TBUpdate', '-e'], check=False).returncode == 1:
            logger.critical('[TB_INSTALLER] ERROR: Failed to run TBUpdate.')
            sys.exit(1)
    else:
        elapsed_time = time.time() - start_time
        minutes, seconds = divmod(elapsed_time, 60)

        if minutes > 0:
            logger.progress(
                f'Toolbase installation finished in {int(minutes)} minutes and {seconds:.2f} seconds)'
            )
        else:
            logger.progress(
                f'Toolbase installation finished in {seconds:.2f} seconds'
            )
        logger.success('[TB_INSTALLER] ALL TOOLS INSTALLED, NO CHANGES.')
        logger.log_phase_header('TOOLBASE INSTALLER - END')


def main():
    args = parse_args()

    # Usage
    install_tools(args.tools_config, args.env_file, args.append_to_env_file)


# Run the main function
if __name__ == '__main__':
    main()
