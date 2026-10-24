"""
Global Modules Package

Provides global utility modules and helper functions.
"""

from .aux_helper import (
    is_running_in_ci,
    load_environment_variables_from_env_file,
    run_command,
)

__all__ = [
    'is_running_in_ci',
    'load_environment_variables_from_env_file',
    'run_command',
]
