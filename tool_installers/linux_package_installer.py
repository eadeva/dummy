# Impor# Import necessary libraries
import argparse
import os
import subprocess
import sys
from pathlib import Path

# TODO: Under construction, TO BE TESTED
# TODO --> what happens in a pipeline/workflow?
from xc_ce_utils import logger
from xc_ce_utils.conf_file_loader.conf_file_loader import (
    get_project_config_root,
)
from xc_ce_utils.json_utils.json_utils import load_json_file

REPO_ROOT = Path(os.getenv('REPO_PATH', Path.cwd()))
LINUX_TOOLS = (
    get_project_config_root(REPO_ROOT)
    / 'tool_installers'
    / 'linux_tools.json'
)


def install_tools_from_json(
    json_file: Path = LINUX_TOOLS,
    env_file=REPO_ROOT / '.env',
    append_to_env_file=False,
):
    """
    Reads tools and their versions from a JSON file and installs them using apt.

    Args:
        json_file (Path): Path to the JSON file containing tools and their versions.

    Raises:
        FileNotFoundError: If the JSON file does not exist.
        RuntimeError: If a tool fails to install.
    """
    # Check if the platform is Linux
    if sys.platform != 'linux':
        logger.critical('This script is only supported on Linux platforms.')
        raise RuntimeError(
            'Unsupported platform. This script can only run on Linux.'
        )

    if not json_file.exists():
        raise FileNotFoundError(f'JSON file not found: {json_file}')

    # Load the JSON file
    logger.progress(f'Loading tools from {json_file}')
    tools = load_json_file(json_file)

    if not tools:
        return

    install_tools(tools, env_file, append_to_env_file)


def install_tools(tools, env_file=REPO_ROOT / '.env', append_to_env_file=False):
    # Update the package list
    logger.progress('Updating package list...')
    subprocess.run(['sudo', 'apt', 'update'], check=True)

    # Install each tool
    for tool, tool_conf in tools.items():
        version = tool_conf.get('version', None)
        package = f'{tool}={version}' if version else tool
        logger.progress(f'Installing {package}...')
        try:
            subprocess.run(
                ['sudo', 'apt', 'install', '-y', package], check=True
            )
            logger.success(f'Successfully installed {package}')
        except subprocess.CalledProcessError as e:
            logger.critical(f'Failed to install {package}. Error: {e}')
            raise RuntimeError(f'Failed to install {package}')


if __name__ == '__main__':
    # Add argument parsing
    parser = argparse.ArgumentParser(
        description='Install Linux tools from a JSON configuration file.'
    )
    parser.add_argument(
        '--config',
        type=str,
        default=str(LINUX_TOOLS),
        help='Path to the JSON file containing tools and their versions (default: config/tool_installers/linux_tools.json).',
    )
    args = parser.parse_args()

    try:
        # Call the function with the provided or default JSON file
        install_tools_from_json(Path(args.config))
    except FileNotFoundError as e:
        logger.critical(e)
        sys.exit(1)
    except RuntimeError as e:
        logger.critical(e)
        sys.exit(1)
    except Exception as e:
        logger.critical(f'Unexpected error: {e}')
        sys.exit(1)
